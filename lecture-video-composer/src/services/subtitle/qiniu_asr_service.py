import argparse
import asyncio
import gzip
import json
import os
import subprocess
import tempfile
import time
import uuid
import websockets
from pathlib import Path

PROTOCOL_VERSION = 0b0001
FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_REQUEST = 0b0010
FULL_SERVER_RESPONSE = 0b1001
SERVER_ACK = 0b1011
SERVER_ERROR_RESPONSE = 0b1111
NO_SEQUENCE = 0b0000
POS_SEQUENCE = 0b0001
NEG_SEQUENCE = 0b0010
NEG_WITH_SEQUENCE = 0b0011
NO_SERIALIZATION = 0b0000
JSON_SERIALIZATION = 0b0001
NO_COMPRESSION = 0b0000
GZIP_COMPRESSION = 0b0001

def generate_header(message_type=FULL_CLIENT_REQUEST,
                    message_type_specific_flags=NO_SEQUENCE,
                    serial_method=JSON_SERIALIZATION,
                    compression_type=GZIP_COMPRESSION,
                    reserved_data=0x00):
    header = bytearray()
    header_size = 1
    header.append((PROTOCOL_VERSION << 4) | header_size)
    header.append((message_type << 4) | message_type_specific_flags)
    header.append((serial_method << 4) | compression_type)
    header.append(reserved_data)
    return header

def generate_before_payload(sequence: int):
    before_payload = bytearray()
    before_payload.extend(sequence.to_bytes(4, 'big', signed=True))
    return before_payload

def parse_response(res):
    if not isinstance(res, bytes):
        return {'payload_msg': res}
    header_size = res[0] & 0x0f
    message_type = res[1] >> 4
    message_type_specific_flags = res[1] & 0x0f
    serialization_method = res[2] >> 4
    message_compression = res[2] & 0x0f
    payload = res[header_size * 4:]
    result = {}
    if message_type_specific_flags & 0x01:
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result['payload_sequence'] = seq
        payload = payload[4:]
    result['is_last_package'] = bool(message_type_specific_flags & 0x02)
    if message_type == FULL_SERVER_RESPONSE:
        payload_size = int.from_bytes(payload[:4], "big", signed=True)
        payload_msg = payload[4:]
    elif message_type == SERVER_ACK:
        seq = int.from_bytes(payload[:4], "big", signed=True)
        result['seq'] = seq
        if len(payload) >= 8:
            payload_size = int.from_bytes(payload[4:8], "big", signed=False)
            payload_msg = payload[8:]
        else:
            payload_msg = b""
    elif message_type == SERVER_ERROR_RESPONSE:
        code = int.from_bytes(payload[:4], "big", signed=False)
        result['code'] = code
        payload_size = int.from_bytes(payload[4:8], "big", signed=False)
        payload_msg = payload[8:]
    else:
        payload_msg = payload

    if message_compression == GZIP_COMPRESSION:
        try:
            payload_msg = gzip.decompress(payload_msg)
        except Exception as e:
            pass
    if serialization_method == JSON_SERIALIZATION:
        try:
            payload_text = payload_msg.decode("utf-8")
            payload_msg = json.loads(payload_text)
        except Exception as e:
            pass
    else:
        payload_msg = payload_msg.decode("utf-8", errors="ignore")
    result['payload_msg'] = payload_msg
    return result

def seconds_to_srt_time(seconds):
    if seconds < 0:
        seconds = 0
    millis = int(seconds * 1000)
    h = millis // 3600000
    m = (millis % 3600000) // 60000
    s = (millis % 60000) // 1000
    ms = millis % 1000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def convert_to_pcm(input_file, output_file=None):
    if output_file is None:
        output_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False).name
    
    cmd = [
        'ffmpeg',
        '-i', str(input_file),
        '-ar', '16000',
        '-ac', '1',
        '-acodec', 'pcm_s16le',
        '-y',
        str(output_file)
    ]
    
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        print(f"音频已转换为: {output_file}")
        return output_file
    except subprocess.CalledProcessError as e:
        print(f"音频转换失败: {e.stderr.decode()}")
        return None
    except FileNotFoundError:
        print("错误: 未找到 ffmpeg。请先安装 ffmpeg:")
        print("  macOS: brew install ffmpeg")
        print("  Ubuntu: sudo apt-get install ffmpeg")
        return None

class QiniuAsrService:
    def __init__(self, token, ws_url, input_file, output_dir, language, seg_duration=300, **kwargs):
        self.token = token
        self.ws_url = ws_url
        self.input_file = Path(input_file)
        self.output_dir = Path(output_dir)
        self.language = language
        self.seg_duration = seg_duration
        self.sample_rate = 16000
        self.channels = 1
        self.bits = 16
        self.format = "pcm"
        self.uid = kwargs.get("uid", "file_asr_user")
        self.codec = kwargs.get("codec", "raw")
        self.temp_wav_file = None

    def construct_request(self):
        req = {
            "user": {"uid": self.uid},
            "audio": {
                "format": self.format,
                "sample_rate": self.sample_rate,
                "bits": self.bits,
                "channel": self.channels,
                "codec": self.codec,
            },
            "request": {
                "model_name": "asr",
                "enable_punc": True,
                "language": self.language
            }
        }
        return req

    async def stream_file(self, file_path):
        bytes_per_frame = self.channels * (self.bits // 8)
        frames_needed = int(self.sample_rate * self.seg_duration / 1000)
        bytes_needed = frames_needed * bytes_per_frame

        with open(file_path, 'rb') as f:
            f.seek(44)
            while True:
                chunk = f.read(bytes_needed)
                if not chunk:
                    break
                yield chunk
                await asyncio.sleep(self.seg_duration / 1000.0 * 0.8)

    async def execute(self):
        print(f"正在处理文件: {self.input_file}")
        self.temp_wav_file = convert_to_pcm(self.input_file)
        if not self.temp_wav_file:
            return

        reqid = str(uuid.uuid4())
        seq = 1
        request_params = self.construct_request()
        payload_bytes = json.dumps(request_params).encode("utf-8")
        payload_bytes = gzip.compress(payload_bytes)
        
        full_client_request = bytearray(generate_header(message_type_specific_flags=POS_SEQUENCE))
        full_client_request.extend(generate_before_payload(sequence=seq))
        full_client_request.extend((len(payload_bytes)).to_bytes(4, "big"))
        full_client_request.extend(payload_bytes)
        
        headers = {"Authorization": "Bearer " + self.token}
        begin_time = time.time()
        subtitles = []
        current_time = 0.0

        try:
            async with websockets.connect(self.ws_url, extra_headers=headers, max_size=1000000000) as ws:
                await ws.send(full_client_request)
                try:
                    res = await asyncio.wait_for(ws.recv(), timeout=10.0)
                except asyncio.TimeoutError:
                    print("等待配置信息响应超时")
                    return
                
                result = parse_response(res)
                print(f"配置响应: {result}")

                async for chunk in self.stream_file(self.temp_wav_file):
                    seq += 1
                    audio_only_request = bytearray(
                        generate_header(message_type=AUDIO_ONLY_REQUEST,
                                        message_type_specific_flags=POS_SEQUENCE))
                    audio_only_request.extend(generate_before_payload(sequence=seq))
                    compressed_chunk = gzip.compress(chunk)
                    audio_only_request.extend((len(compressed_chunk)).to_bytes(4, "big"))
                    audio_only_request.extend(compressed_chunk)
                    
                    await ws.send(audio_only_request)
                    
                    try:
                        res = await asyncio.wait_for(ws.recv(), timeout=5.0)
                        result = parse_response(res)
                        
                        if isinstance(result.get('payload_msg'), dict):
                            data = result['payload_msg'].get('data', {})
                            asr_result = data.get('result', {})
                            text = asr_result.get('text', '').strip()
                            
                            if text:
                                start_time = current_time
                                end_time = current_time + (self.seg_duration / 1000.0)
                                
                                print(f"[{seconds_to_srt_time(start_time)} --> {seconds_to_srt_time(end_time)}] {text}")
                                
                                subtitles.append({
                                    'start': start_time,
                                    'end': end_time,
                                    'text': text
                                })
                        
                        current_time += (self.seg_duration / 1000.0)
                        
                    except asyncio.TimeoutError:
                        pass

                seq += 1
                final_request = bytearray(
                    generate_header(message_type=AUDIO_ONLY_REQUEST,
                                    message_type_specific_flags=NEG_WITH_SEQUENCE))
                final_request.extend(generate_before_payload(sequence=seq))
                final_request.extend((0).to_bytes(4, "big"))
                await ws.send(final_request)

                try:
                    res = await asyncio.wait_for(ws.recv(), timeout=5.0)
                    result = parse_response(res)
                    print(f"最终响应: {result}")
                except asyncio.TimeoutError:
                    pass

        except Exception as e:
            print(f"异常: {e}")
            import traceback
            traceback.print_exc()
        finally:
            elapsed = time.time() - begin_time
            print(f"处理完成，耗时: {elapsed:.2f} 秒")
            
            self.save_srt(subtitles)
            
            if self.temp_wav_file and os.path.exists(self.temp_wav_file):
                os.remove(self.temp_wav_file)
                print(f"已清理临时文件: {self.temp_wav_file}")

    def save_srt(self, subtitles):
        if not subtitles:
            print("没有识别到任何文本，不创建 SRT 文件。")
            return
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self.output_dir / (self.input_file.stem + ".srt")
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                for i, sub in enumerate(subtitles, 1):
                    f.write(f"{i}\n")
                    f.write(f"{seconds_to_srt_time(sub['start'])} --> {seconds_to_srt_time(sub['end'])}\n")
                    f.write(f"{sub['text']}\n\n")
            
            print(f"✅ SRT 字幕文件已保存到: {output_path}")
        except Exception as e:
            print(f"保存 SRT 文件失败: {e}")

    def run(self):
        asyncio.run(self.execute())

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="七牛云 ASR 语音识别服务")
    parser.add_argument('input_file', help='输入音频文件路径')
    parser.add_argument('--output-dir', default='output/subtitles', help='输出目录')
    parser.add_argument('--language', default='zh', choices=['zh', 'en'], help='识别语言')
    parser.add_argument('--token', default=os.getenv('QINIU_TOKEN'), help='七牛云 API Token')
    parser.add_argument('--ws-url', default='wss://api.qnaigc.com/v1/voice/asr', help='WebSocket 服务地址')
    parser.add_argument('--seg-duration', type=int, default=300, help='分段时长（毫秒）')
    
    args = parser.parse_args()
    
    if not args.token:
        print("错误: 请通过 --token 参数或 QINIU_TOKEN 环境变量提供 API Token")
        exit(1)
    
    client = QiniuAsrService(
        token=args.token,
        ws_url=args.ws_url,
        input_file=args.input_file,
        output_dir=args.output_dir,
        language=args.language,
        seg_duration=args.seg_duration
    )
    client.run()



