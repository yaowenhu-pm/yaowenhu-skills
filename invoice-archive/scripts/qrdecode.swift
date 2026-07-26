import Foundation
import CoreImage

for path in CommandLine.arguments.dropFirst() {
    guard let img = CIImage(contentsOf: URL(fileURLWithPath: path)) else { print(path, "-> 无法读取"); continue }
    let d = CIDetector(ofType: CIDetectorTypeQRCode, context: nil, options: [CIDetectorAccuracy: CIDetectorAccuracyHigh])!
    let feats = d.features(in: img).compactMap { ($0 as? CIQRCodeFeature)?.messageString }
    print((path as NSString).lastPathComponent, "->", feats.isEmpty ? "无二维码" : feats.joined(separator: " | "))
}
