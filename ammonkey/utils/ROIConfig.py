import cv2
import json
import os

def get_frame(video_path, frame_number):
    """Fetch a specific frame from the video."""
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise ValueError(f"Frame {frame_number} could not be read from {video_path}")
    return frame

def draw_roi(video_path, frame_number, roi_store='roi_config.json'):
    """Allow user to draw ROI and store it in a JSON file."""
    frame = get_frame(video_path, frame_number)
    rois = {} #if not os.path.exists(roi_store) else json.load(open(roi_store))
    
    def mouse_callback(event, x, y, flags, param):
        nonlocal roi, drawing
        if event == cv2.EVENT_LBUTTONDOWN:
            roi = [(x, y)]
            drawing = True
        elif event == cv2.EVENT_LBUTTONUP:
            roi.append((x, y))
            drawing = False
            cv2.rectangle(frame, roi[0], roi[1], (0, 255, 0), 2)
            cv2.imshow('Select ROI', frame)
    
    roi, drawing = [], False
    cv2.imshow('Select ROI', frame)
    cv2.setMouseCallback('Select ROI', mouse_callback)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    
    if len(roi) == 2:
        x1, y1, x2, y2 = *roi[0], *roi[1]
        roi_coords = [min(x1, x2), min(y1, y2), abs(x2 - x1), abs(y2 - y1)]
        rois[video_path] = roi_coords
        #with open(roi_store, 'w') as f:
            #json.dump(rois, f, indent=4)
            # pass
        #print(f"ROI saved for {video_path}: {roi_coords}")
        return roi_coords
    else:
        print("No ROI selected.")
        return None

def show_saved_rois(video_path, ROI = [0,0,5,5], frame = 0):
    """Display the saved ROI on a frame."""
    x, y, w, h = ROI
    frame = get_frame(video_path, 0)  # Show first frame by default
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.imshow('Saved ROI', frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    print(f"Showing saved ROI: {os.path.basename(video_path)}, {ROI}")

if __name__ == "__main__":
    # video_file = input("Enter video path: ")
    vids = ["C:\\Users\\rnel\\Videos\\C0629.MP4"]#,
            #"P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250206\\cam2\\C0444.mp4",
            #"P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250206\\cam3\\C0551.mp4",
            #"P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250206\\cam4\\C0594.mp4"
            #]
    for video_file in vids:
        choice = input("[1] Draw new ROI\n[2] Show saved ROI\nChoose: ")
        if choice == '1':
            frame_num = int(input("Enter frame number to preview: "))
            draw_roi(video_file, frame_num)
        elif choice == '2':
            show_saved_rois(video_file)
        else:
            print("Invalid option.")
