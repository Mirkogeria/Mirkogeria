// Trova i punti del viso (occhi, sopracciglia, naso, bocca, contorno) con il
// riconoscimento dei volti di macOS e li scrive in JSON, in pixel dell'immagine
// con l'origine in alto a sinistra. Funziona solo su Mac, in locale:
//
//     swift scripts/face_landmarks.swift foto.png landmarks.json
//
// make_portrait.py --landmarks landmarks.json li usa per disegnare i lineamenti
// come linee pulite invece di ricavarli dalle sfumature della foto.

import AppKit
import CoreImage
import Foundation
import Vision

let args = CommandLine.arguments
guard args.count == 3 else {
    print("uso: swift face_landmarks.swift foto.png landmarks.json")
    exit(1)
}
let input = URL(fileURLWithPath: args[1])
let output = URL(fileURLWithPath: args[2])

guard var image = CIImage(contentsOf: input, options: [.applyOrientationProperty: true]) else {
    print("immagine non leggibile")
    exit(1)
}
// se lo sfondo e trasparente lo appoggio su bianco: il riconoscimento lavora meglio
let white = CIImage(color: .white).cropped(to: image.extent)
image = image.composited(over: white)
let size = image.extent.size

let request = VNDetectFaceLandmarksRequest()
try VNImageRequestHandler(ciImage: image).perform([request])
guard let face = request.results?.max(by: { $0.boundingBox.width < $1.boundingBox.width }),
      let lm = face.landmarks else {
    print("nessun volto trovato")
    exit(1)
}

let regions: [String: VNFaceLandmarkRegion2D?] = [
    "faceContour": lm.faceContour, "leftEye": lm.leftEye, "rightEye": lm.rightEye,
    "leftEyebrow": lm.leftEyebrow, "rightEyebrow": lm.rightEyebrow,
    "nose": lm.nose, "noseCrest": lm.noseCrest, "medianLine": lm.medianLine,
    "outerLips": lm.outerLips, "innerLips": lm.innerLips,
    "leftPupil": lm.leftPupil, "rightPupil": lm.rightPupil,
]
var out: [String: Any] = ["width": size.width, "height": size.height]
var points: [String: [[Double]]] = [:]
for (name, region) in regions {
    guard let region else { continue }
    points[name] = region.pointsInImage(imageSize: size).map { [Double($0.x), Double(size.height - $0.y)] }
}
out["regions"] = points
let bb = face.boundingBox
out["box"] = [bb.minX * size.width, (1 - bb.maxY) * size.height, bb.width * size.width, bb.height * size.height]
try JSONSerialization.data(withJSONObject: out, options: [.prettyPrinted, .sortedKeys]).write(to: output)
print("ok: \(points.count) zone del viso -> \(output.lastPathComponent)")
