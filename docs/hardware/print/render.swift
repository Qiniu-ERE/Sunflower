// 效果图：读 model.py --scene 写出的场景，用 SceneKit 离屏渲染成 PNG（只在 macOS 上能跑）。
//
//     swift docs/hardware/print/render.swift <场景目录> <输出.png> [hero|side|back|explode]
//     explode 视角配 <key>-exploded 场景（model.py --scene 同时写出）
import AppKit
import SceneKit

let args = CommandLine.arguments
let dir = URL(fileURLWithPath: args[1])
let out = URL(fileURLWithPath: args[2])
let view = args.count > 3 ? args[3] : "hero"
let W = 1600, H = 1200

func color(_ hex: String) -> NSColor {
    var v: UInt64 = 0
    Scanner(string: String(hex.dropFirst())).scanHexInt64(&v)
    return NSColor(srgbRed: CGFloat((v >> 16) & 255) / 255, green: CGFloat((v >> 8) & 255) / 255,
                   blue: CGFloat(v & 255) / 255, alpha: 1)
}

func load(_ url: URL) -> SCNGeometry {
    let d = try! Data(contentsOf: url)
    let nv = Int(d.withUnsafeBytes { $0.load(fromByteOffset: 0, as: UInt32.self) })
    let nt = Int(d.withUnsafeBytes { $0.load(fromByteOffset: 4, as: UInt32.self) })
    let pos = d.subdata(in: 8..<(8 + nv * 12))
    let nrm = d.subdata(in: (8 + nv * 12)..<(8 + nv * 24))
    let idx = d.subdata(in: (8 + nv * 24)..<(8 + nv * 24 + nt * 12))
    let src = { (data: Data, sem: SCNGeometrySource.Semantic) in
        SCNGeometrySource(data: data, semantic: sem, vectorCount: nv, usesFloatComponents: true,
                          componentsPerVector: 3, bytesPerComponent: 4, dataOffset: 0, dataStride: 12)
    }
    let el = SCNGeometryElement(data: idx, primitiveType: .triangles, primitiveCount: nt, bytesPerIndex: 4)
    return SCNGeometry(sources: [src(pos, .vertex), src(nrm, .normal)], elements: [el])
}

let spec = try! JSONSerialization.jsonObject(with: Data(contentsOf: dir.appendingPathComponent("scene.json")))
    as! [String: Any]
let scene = SCNScene()
let bg = color("#FBF6EA")
scene.background.contents = bg
for item in spec["items"] as! [[String: Any]] {
    let g = load(dir.appendingPathComponent(item["file"] as! String))
    let m = SCNMaterial()
    m.lightingModel = .physicallyBased
    m.diffuse.contents = color(item["color"] as! String)
    m.roughness.contents = item["roughness"] as! Double
    m.metalness.contents = 0.0
    m.isDoubleSided = false
    g.materials = [m]
    scene.rootNode.addChildNode(SCNNode(geometry: g))
}

// 地面：只接影子（SCNFloor 默认在 XZ 平面，转到 XY）
let floor = SCNFloor()
floor.reflectivity = 0
let fm = SCNMaterial()
fm.lightingModel = .shadowOnly
floor.materials = [fm]
let floorNode = SCNNode(geometry: floor)
floorNode.eulerAngles.x = .pi / 2
scene.rootNode.addChildNode(floorNode)

func light(_ type: SCNLight.LightType, _ intensity: CGFloat, _ temp: CGFloat, at p: SCNVector3?, shadow: Bool = false) {
    let l = SCNLight()
    l.type = type
    l.intensity = intensity
    l.temperature = temp
    let n = SCNNode()
    n.light = l
    if let p = p {
        n.position = p
        n.look(at: SCNVector3(0, 0, 110), up: SCNVector3(0, 0, 1), localFront: SCNVector3(0, 0, -1))
    }
    if shadow {
        l.castsShadow = true
        l.shadowMode = .deferred
        l.shadowMapSize = CGSize(width: 4096, height: 4096)
        l.shadowRadius = 12
        l.shadowSampleCount = 64
        l.shadowBias = 2
        l.orthographicScale = 220
        l.shadowColor = NSColor(white: 0, alpha: 0.28)
        l.automaticallyAdjustsShadowProjection = false
        l.zNear = 10
        l.zFar = 1200
    }
    scene.rootNode.addChildNode(n)
}

light(.ambient, 520, 6000, at: nil)
light(.directional, 1250, 5600, at: SCNVector3(-260, -380, 520), shadow: true)
light(.directional, 420, 7000, at: SCNVector3(360, -160, 220))
light(.directional, 520, 6500, at: SCNVector3(80, 420, 360))

let cam = SCNCamera()
cam.fieldOfView = 21
cam.zNear = 10
cam.zFar = 3000
cam.wantsHDR = true
cam.wantsExposureAdaptation = false
cam.exposureOffset = -0.1
cam.screenSpaceAmbientOcclusionIntensity = 0
cam.screenSpaceAmbientOcclusionRadius = 6
let camNode = SCNNode()
camNode.camera = cam
let views: [String: (SCNVector3, SCNVector3)] = [
    "hero": (SCNVector3(-300, -560, 300), SCNVector3(0, 0, 118)),
    "side": (SCNVector3(-650, 0, 160), SCNVector3(0, 0, 112)),
    "back": (SCNVector3(280, 560, 330), SCNVector3(0, 0, 112)),
    "explode": (SCNVector3(-820, -520, 420), SCNVector3(0, 0, 150)),
]
let (eye, target) = views[view]!
if view == "explode" { cam.fieldOfView = 23 }
camNode.position = eye
camNode.look(at: target, up: SCNVector3(0, 0, 1), localFront: SCNVector3(0, 0, -1))
scene.rootNode.addChildNode(camNode)

let r = SCNRenderer(device: MTLCreateSystemDefaultDevice(), options: nil)
r.scene = scene
r.pointOfView = camNode
let img = r.snapshot(atTime: 0, with: CGSize(width: W, height: H), antialiasingMode: .multisampling4X)
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: out)
print("写出 \(out.path)")
