import cv2 # Computer vision
import numpy as np # To hold numerical operations related to face_recognition
import smbus # To enable I2C communication between the RPi and the LCD
import face_recognition as fr # Face_recognition on the image
import os # For system directory and files
from time import sleep  #FOR TIME PURPOSES
import pandas as pd # for accessing the excel file
import qrcode # to generate the qr
import smtplib # To send emails
from email.mime.multipart import MIMEMultipart # complex email message
from email.mime.text import MIMEText # To write text in email
from email.mime.base import MIMEBase # To be able to attach file on email
from email import encoders # Encode the qr data
from pyzbar.pyzbar import decode # Decode the QR data
from gpiozero import LED, DistanceSensor # for hardware components initialization
from datetime import datetime, timedelta
 
# Credentials come from environment variables (never hardcode them)
SENDER_EMAIL = os.environ["SENDER_EMAIL"]
SMTP_PASSWORD = os.environ["SMTP_PASSWORD"]

# Hardware Components
gled = LED(27)
rled = LED(23) 
sensor = DistanceSensor(echo=18 , trigger=17)
 
# LCD Configuration
I2C_ADDR = 0x27
LCD_WIDTH = 16  # Characters per line
LCD_CHR = 1  # Sending data
LCD_CMD = 0  # Sending commands
LCD_LINE_1 = 0x80  # Address for first line
LCD_LINE_2 = 0xC0  # Address for second line
LCD_BACKLIGHT = 0x08  # Backlight ON
CLEAR_DISPLAY = 0x01
ENABLE = 0b00000100  # Enable bit
 
# Initialize the I2C bus
bus = smbus.SMBus(1) # bus number
def lcd_init():
   lcd_byte(0x33, LCD_CMD)  # Initialize
   lcd_byte(0x32, LCD_CMD)  # Set to 4-bit mode
   lcd_byte(0x06, LCD_CMD)  # Cursor move direction
   lcd_byte(0x0C, LCD_CMD)  # Display ON, Cursor OFF
   lcd_byte(0x28, LCD_CMD)  # 2-line, 5x7 matrix
   lcd_byte(0x01, LCD_CMD)  # Clear display
   sleep(0.2)
 
def lcd_byte(bits, mode):
   bits_high = mode | (bits & 0xF0) | LCD_BACKLIGHT
   bits_low = mode | ((bits << 4) & 0xF0) | LCD_BACKLIGHT
   # Send high bits
   bus.write_byte(I2C_ADDR, bits_high)
   lcd_toggle_enable(bits_high)
   # Send low bits
   bus.write_byte(I2C_ADDR, bits_low)
   lcd_toggle_enable(bits_low)
 
def lcd_toggle_enable(bits):
   sleep(0.0005)
   bus.write_byte(I2C_ADDR, (bits | ENABLE))
   sleep(0.0005)
   bus.write_byte(I2C_ADDR, (bits & ~ENABLE))
   sleep(0.0005)
 
def lcd_string(message, line):
   message = message.ljust(LCD_WIDTH, " ")
   lcd_byte(line, LCD_CMD)
   for char in message:
       lcd_byte(ord(char), LCD_CHR)
       
lcd_init()      

# Load student data from Excel
file_path = os.environ.get("ROSTER_PATH", "data/students.xlsx")  
print("Loading student data from Excel...")
df = pd.read_excel(file_path, engine='openpyxl') # Use Pandas to read the excel

# Ensure required columns exist
required_columns = {"Name", "ID", "Email", "SessionID", "Status"} # Needed columns for operation
if not required_columns.issubset(df.columns):
    raise ValueError("Excel file must contain 'Name', 'ID', 'Email', 'SessionID', and 'Status' columns.")


# Add QR Token column if not present
if "QR Token" not in df.columns:
    df["QR Token"] = ""
 
def send_qr_code(email, qr_token):
    print(f"Sending QR code to {email}...")
    qr = qrcode.make(qr_token) # Making the QR according to the token(specified later)
    qr_path = f"QR_{email}.png" # Writing the name of the image
    qr.save(qr_path) # Save the QR
    msg = MIMEMultipart() # Enabling complex email messages
    msg['From'] = SENDER_EMAIL
    msg['To'] = email
    msg['Subject'] = "Your Secure Attendance QR Code" # Header of the email
    body = "Please find attached your QR code for attendance."
    msg.attach(MIMEText(body, 'plain'))
    attachment = open(qr_path, "rb")
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(attachment.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f"attachment; filename={qr_path}")
    msg.attach(part)
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(SENDER_EMAIL, SMTP_PASSWORD)
    text = msg.as_string()
    server.sendmail(SENDER_EMAIL, email, text)
    server.quit()
    print("QR code sent successfully.")
    
# QR Code Scanning Function
def scan_qr():
    lcd_string("Scan QR", LCD_LINE_1)
    lcd_string("", LCD_LINE_2)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Error: Could not open webcam for QR scanning.")
        return None
    
    print("Starting QR code scan...")
    
    while True:
        success, img = cap.read()
        
        if not success or img is None:
            print("Error: Failed to capture image from webcam.")
            break

        for barcode in decode(img):

            qr_data = barcode.data.decode('utf-8')
            print(f"QR Code Detected: {qr_data}")
            cap.release()
            cv2.destroyAllWindows()
            return qr_data
            
        cv2.imshow('QR Scanner', img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    return


# Send QR code before scanning
# Function to send QR code to student
class_start_time = datetime(2025, 2, 12, 14,31, 0) 
qr_send_time = class_start_time - timedelta(minutes=1)
# Wait until the time to send QR codes
while datetime.now() < qr_send_time:
    sleep(2)  # Check every 10 seconds
    
# Send QR codes to all students
df.apply(lambda row: send_qr_code(row["Email"], row["QR Token"]), axis=1)
 
# Face Recognition Setup
print("Loading face recognition dataset...")
path = os.environ.get("PICS_PATH", "pics")
images = []
classNames = []
mylist = os.listdir(path)

for cls in mylist:
    curImg = cv2.imread(f'{path}/{cls}')
    if curImg is not None:
        images.append(curImg)
        classNames.append(os.path.splitext(cls)[0])
    else:
        print(f"Warning: Failed to load image {cls}")
        
        
def findEncodings(images):
    encodeList = []
    for img in images:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encode = fr.face_encodings(img)

        if encode:  # Check if face encodings are found
            encodeList.append(encode[0])
            
    return encodeList

print("Encoding known faces...")
encodeListKnown = findEncodings(images)
print("Face encoding complete.")

try:
 
    while True:
 
        class_start_time = datetime(2025, 2, 12, 14, 39, 0)  # Class starts at 10:00 AM
        attendance_window_end = class_start_time + timedelta(minutes=50)  # 15-minute window for attendance
        while datetime.now() < attendance_window_end:
 
            cm = sensor.distance * 100  # Check distance
            print(cm)
            
            if cm < 30:
                qr_token = scan_qr()
            else:
                print("No Student detected. Restarting process...")
                lcd_string("No Student detected", LCD_LINE_1)
                lcd_string("", LCD_LINE_2)
                sleep(3)
                continue
            
            # Verify QR Code in Excel
            df_match = df[df["QR Token"] == qr_token]
            if df_match.empty:
                rled.on()
                sleep(9)
                rled.off()
                print("Invalid QR Code. Access Denied. Restarting process...")
                lcd_string("Invalid QR", LCD_LINE_1)
                lcd_string("Access Denied", LCD_LINE_2)
                sleep(5)
                continue
            else:
                student_name = df_match.iloc[0]["Name"]
                student_id = df_match.iloc[0]["ID"]
                print(f"QR Code Verified. Welcome, {student_name}!")
                lcd_string("QR Verified", LCD_LINE_1)
                sleep(3)
                lcd_string("Welcome", LCD_LINE_1)
                lcd_string(f"{student_name}", LCD_LINE_2)
                sleep(3)
                
                # Face Recognition
                print("Starting webcam for face recognition...")
                lcd_string(" ", LCD_LINE_2)
                lcd_string("Face recognition", LCD_LINE_1)
                cap = cv2.VideoCapture(0)
 
                if not cap.isOpened():
                    print("Error: Could not open webcam for face recognition.")
                    continue
                
                while True:
                    success, img = cap.read()
                    if not success or img is None:
                        print("Error: Failed to capture image from webcam. Restarting process...")
                        cap.release()
                        cv2.destroyAllWindows()
                        break

                    imgSmall = cv2.resize(img, (0, 0), None, 0.25, 0.25)
                    imgSmall = cv2.cvtColor(imgSmall, cv2.COLOR_BGR2RGB)
                    facesCurFrame = fr.face_locations(imgSmall)
                    encodesCurFrame = fr.face_encodings(imgSmall, facesCurFrame)
                    print(f"Detected {len(facesCurFrame)} face(s) in frame.")
 
                    for encodeFace, faceLoc in zip(encodesCurFrame, facesCurFrame):
                        matches = fr.compare_faces(encodeListKnown, encodeFace)
                        FaceDis = fr.face_distance(encodeListKnown, encodeFace)
                        matchindex = np.argmin(FaceDis)
                        
                        if matches[matchindex]:
                            name = classNames[matchindex]
                            if name == student_name:
                                gled.on()
                                sleep(3)
                                gled.off()
                                print(f"Face Recognized: {name}")
                                df.loc[df["ID"] == student_id, "Status"] = "Attend"
                                attendance_count = df[df["Status"] == "Attend"].shape[0]
                                df.to_excel(file_path, index=False) # Write row names
                                print(f"Excel updated: {student_name} marked as 'Attend'.")
                                lcd_string(f"{student_name}", LCD_LINE_1)
                                lcd_string(f"Attend", LCD_LINE_2)
                                sleep(3)
                                lcd_string(f"Total Attendees:", LCD_LINE_1)
                                lcd_string(f"{attendance_count}", LCD_LINE_2)
                                sleep(4)
                                cap.release()
                                cv2.destroyAllWindows()
                                break  # Exit face recognition loop

                            else:
                                rled.on()
                                sleep(3)
                                print("Face does not match QR Code. Access Denied.")
                                lcd_string("Face doesn't", LCD_LINE_1)
                                lcd_string("match", LCD_LINE_2)
                                sleep(3)
                                cap.release()
                                cv2.destroyAllWindows()
                                break  # Exit face recognition loop

                    cv2.imshow('WebCam', img)

                    if cv2.waitKey(1) & 0xFF == ord('q'):
 
                        break
                cap.release()
                cv2.destroyAllWindows()
        # Check if the attendance time window has ended
 
        if datetime.now() >= attendance_window_end:
            print("Attendance window closed.")
            lcd_string("Time's up", LCD_LINE_1)
            lcd_string("Attendance Closed", LCD_LINE_2)
            sleep(5)
            break  # Exit the main loop to end the process
        
except Exception as e:
 
    print(f"An error occurred: {e}")
 
    lcd_string("Error Occurred", LCD_LINE_1)
 
    lcd_string(f"{str(e)}", LCD_LINE_2)
 
    sleep(5)
 
 
