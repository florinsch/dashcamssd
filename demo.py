from __future__ import print_function
import torch
from torch.autograd import Variable
import cv2
import time
import imutils
from imutils.video import FPS, FileVideoStream
import argparse

from data import BaseTransform, VOC_CLASSES as labelmap
from ssd import build_ssd

parser = argparse.ArgumentParser(description='Single Shot MultiBox Detection')
parser.add_argument('--weights', default='weights/ssd300_mAP_77.43_v2.pth',  # ssd_300_VOC0712.pth
                    type=str, help='Trained state_dict file path.')
parser.add_argument('--video', default='dashcam.mp4', type=str, help='Video to process.')
parser.add_argument('--threshold', default=0.2, type=float, help='Threshold to filter detections.')
parser.add_argument('--cuda', default=False, type=bool,
                    help='Use cuda.')
args = parser.parse_args()

COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
FONT = cv2.FONT_HERSHEY_SIMPLEX


def cv2_demo(net, transform, stream):
    is_cuda = next(net.parameters()).is_cuda

    def predict(frame):
        height, width = frame.shape[:2]
        x = torch.from_numpy(transform(frame)[0]).permute(2, 0, 1)
        y = net(Variable(x.unsqueeze(0).cuda() if is_cuda else x.unsqueeze(0)))  # forward pass
        detections = y.data
        # scale each detection back up to the image
        scale = torch.Tensor([width, height, width, height])
        for i in range(detections.size(1)):
            j = 0
            while detections[0, i, j, 0] >= args.threshold:
                pt = (detections[0, i, j, 1:] * scale).cpu().numpy()
                cv2.rectangle(frame, (int(pt[0]), int(pt[1])), (int(pt[2]),
                                                                int(pt[3])), COLORS[i % 3], 2)
                cv2.putText(frame, labelmap[i - 1], (int(pt[0]), int(pt[1])), FONT,
                            1.5, (0, 0, 0), 2, cv2.LINE_AA)
                cv2.putText(frame, labelmap[i - 1], (int(pt[0]), int(pt[1])), FONT,
                            1.5, (255, 255, 255), 2, cv2.LINE_AA)
                j += 1
        return frame

    # start video stream thread, allow buffer to fill
    print("[INFO] starting threaded video stream...")
    time.sleep(1.0)
    # start fps timer
    # loop over frames from the video file stream
    c = -1
    while True:
        c += 1
        # grab next frame
        if c % 10 == 0:
            frame = stream.read()
            # frame = imutils.resize(frame, width=350)
        else:
            continue
        key = cv2.waitKey(1) & 0xFF

        # update FPS counter
        fps.update()
        frame = predict(frame)

        # keybindings for display
        if key == ord('p'):  # pause
            while True:
                key2 = cv2.waitKey(1) or 0xff
                cv2.imshow('frame', frame)
                if key2 == ord('p'):  # resume
                    break
        cv2.imshow('frame', frame)
        if key == 27:  # exit
            break


if __name__ == '__main__':
    import sys
    from os import path
    sys.path.append(path.dirname(path.dirname(path.abspath(__file__))))

    if args.cuda:
        if torch.cuda.is_available():
            current = torch.cuda.current_device()
            print("Using CUDA device #{} {}".format(current, torch.cuda.get_device_name(current)))
            torch.set_default_tensor_type('torch.cuda.FloatTensor')
        else:
            raise EnvironmentError("Cuda not available on your platform!")

    net = build_ssd('test', 300, 21)    # initialize SSD
    net.load_state_dict(torch.load(args.weights, map_location=lambda storage, loc: storage))
    transform = BaseTransform(net.size, (104 / 256.0, 117 / 256.0, 123 / 256.0))

    stream = FileVideoStream(args.video).start()
    # stream.stream.set(cv2.CAP_PROP_FPS, 1)
    fps = FPS().start()
    # stop the timer and display FPS information
    cv2_demo(net.eval(), transform, stream)
    fps.stop()

    print("[INFO] elapsed time: {:.2f}".format(fps.elapsed()))
    print("[INFO] approx. FPS: {:.2f}".format(fps.fps()))

    # cleanup
    cv2.destroyAllWindows()
    stream.stop()
