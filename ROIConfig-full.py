import cv2
import json
import os
import matplotlib.pyplot as plt

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
        with open(roi_store, 'w') as f:
            json.dump(rois, f, indent=4)
            # pass
        print(f"ROI saved for {video_path}: {roi_coords}")

        # Extract the selected ROI from the frame
        roi_frame = frame[roi_coords[1]:roi_coords[1] + roi_coords[3], roi_coords[0]:roi_coords[0] + roi_coords[2]]
        
        # Convert to HSV
        hsv_frame = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2HSV)
        
        # Flatten the arrays to plot histogram
        h_values, s_values, v_values = hsv_frame[:,:,0].flatten(), hsv_frame[:,:,1].flatten(), hsv_frame[:,:,2].flatten()
        
        # Remove points where HSV == (60, 255, 255)
        mask = ~((h_values == 60) & (s_values == 255) & (v_values == 255))
        h_values, s_values, v_values = h_values[mask], s_values[mask], v_values[mask]
    
        # Convert HSV to 360, 100%, 100% scale
        h_values = h_values * 2  # Hue range 0-360
        s_values = s_values / 255 * 100  # Saturation 0-100%
        v_values = v_values / 255 * 100  # Value 0-100%
        
        # Plot HSV distribution
        plt.figure(figsize=(12, 4))
        plt.subplot(1, 3, 1)
        plt.hist(h_values, bins=50, color='r', alpha=0.7)
        plt.title("Hue Distribution")
        
        plt.subplot(1, 3, 2)
        plt.hist(s_values, bins=50, color='g', alpha=0.7)
        plt.title("Saturation Distribution")
        
        plt.subplot(1, 3, 3)
        plt.hist(v_values, bins=50, color='b', alpha=0.7)
        plt.title("Value Distribution")
        
        plt.show()
    else:
        print("No ROI selected.")

def show_saved_rois(video_path, roi_store='roi_config.json'):
    """Display the saved ROI on a frame."""
    if not os.path.exists(roi_store):
        print("No saved ROIs found.")
        return
    
    with open(roi_store) as f:
        rois = json.load(f)
    
    if video_path not in rois:
        print(f"No ROI saved for {video_path}")
        return
    
    x, y, w, h = rois[video_path]
    frame = get_frame(video_path, 0)  # Show first frame by default
    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
    cv2.imshow('Saved ROI', frame)
    cv2.waitKey(0)
    cv2.destroyAllWindows()
    print(f"Showing saved ROI: {roi}")

if __name__ == "__main__":
    # video_file = input("Enter video path: ")
    vids = ["C:\\Users\\rnel\\Videos\\C0629.MP4",
            "C:\\Users\\rnel\\Videos\\C0670.MP4",]
           # #"P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250210\\cam3\\C0563.mp4",
           # "P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250210\\cam4\\C0606.mp4"
           #]
    #vids = ["P:\\projects\\monkeys\\Chronic_VLL\\DATA_RAW\\Pici\\2025\\02\\20250211\\cam1\\C0412.mp4"]
    for video_file in vids:
        choice = input("[1] Draw new ROI\n[2] Show saved ROI\nChoose: ")
        if choice == '1':
            frame_num = int(input("Enter frame number to preview: "))
            draw_roi(video_file, frame_num)
        elif choice == '2':
            show_saved_rois(video_file)
        else:
            print("Invalid option.")
