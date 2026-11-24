# Face detector model

Primary model: `face_detection_yunet_2023mar.onnx`

- Upstream: OpenCV Zoo YuNet, <https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet>
- Downloaded: 2026-11-16
- SHA-256: `8F2383E4DD3CFBB4553EA8718107FC0423210DC964F9F4280604804ED2552FA4`
- License: Apache License 2.0; local copy in `OPENCV_ZOO_LICENSE.txt`
- Purpose: human-face detection only. It is not an animal-face detector and is not used for identity recognition.

`lbpcascade_frontalface_opencv.xml` is retained only as a compatibility fallback when YuNet or `FaceDetectorYN` cannot be loaded. A zero-face YuNet result does **not** trigger the fallback.
