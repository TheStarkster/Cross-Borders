import socket
import pyautogui
import json
from pynput import mouse
import threading
import tkinter as tk
from tkinter import messagebox

# Disable failsafe
pyautogui.FAILSAFE = False

class MouseServer:
    def __init__(self):
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = socket.gethostname()
        self.port = 12345
        self.is_running = False
        self.client = None
        self.listener = None
        self.mouse_pressed = False
        
    def start_server(self):
        try:
            self.server.bind((self.host, self.port))
            self.server.listen(1)
            self.is_running = True
            print(f"Server started on {self.host}:{self.port}")
            
            # Create GUI window
            self.root = tk.Tk()
            self.root.title("Cross-Border Mouse Control")
            self.root.geometry("300x200")
            
            # Add status label
            self.status_label = tk.Label(self.root, text="Waiting for connection...", pady=20)
            self.status_label.pack()
            
            # Add stop button
            stop_button = tk.Button(self.root, text="Stop Server", command=self.stop_server)
            stop_button.pack()
            
            # Start accepting connections in a separate thread
            threading.Thread(target=self.accept_connections, daemon=True).start()
            
            self.root.mainloop()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server: {str(e)}")
            
    def accept_connections(self):
        while self.is_running:
            try:
                self.client, addr = self.server.accept()
                self.status_label.config(text=f"Connected to {addr[0]}")
                print(f"Connection from {addr}")
                self.start_mouse_tracking()
            except:
                if self.is_running:
                    continue
                break

    def on_click(self, x, y, button, pressed):
        if self.client and self.is_running:
            try:
                data = json.dumps({
                    "type": "click",
                    "button": str(button),
                    "pressed": pressed
                }) + "\n"
                self.client.send(data.encode())
            except Exception as e:
                print(f"Error sending click: {str(e)}")
                
    def start_mouse_tracking(self):
        def on_move(x, y):
            if self.client and self.is_running:
                try:
                    # Get screen size
                    screen_width, screen_height = pyautogui.size()
                    
                    # Check if mouse is at extreme left
                    if x <= 0:
                        # Send signal to move mouse to right side of Windows
                        data = json.dumps({
                            "type": "move",
                            "x_percent": 0.99,  # Almost right edge
                            "y_percent": y / screen_height
                        }) + "\n"
                    else:
                        # Normal mouse movement
                        data = json.dumps({
                            "type": "move",
                            "x_percent": x / screen_width,
                            "y_percent": y / screen_height
                        }) + "\n"
                    self.client.send(data.encode())
                except Exception as e:
                    print(f"Error sending coordinates: {str(e)}")
                    
        # Stop existing listeners if any
        if self.listener:
            self.listener.stop()
            
        # Start mouse listeners for both movement and clicks
        self.listener = mouse.Listener(
            on_move=on_move,
            on_click=self.on_click)
        self.listener.start()
        
    def stop_server(self):
        self.is_running = False
        if self.listener:
            self.listener.stop()
        if self.client:
            self.client.close()
        self.server.close()
        self.root.quit()
        
class MouseClient:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buffer = ""
        
    def connect_to_server(self, host):
        try:
            self.client.connect((host, 12345))
            print("Connected to server")
            
            # Get screen size once
            screen_width, screen_height = pyautogui.size()
            
            while True:
                try:
                    # Receive data and add to buffer
                    chunk = self.client.recv(1024).decode()
                    if not chunk:
                        break
                        
                    self.buffer += chunk
                    
                    # Process complete messages
                    while "\n" in self.buffer:
                        message, self.buffer = self.buffer.split("\n", 1)
                        data = json.loads(message)
                        
                        if data["type"] == "move":
                            # Convert percentages back to actual coordinates
                            x = int(data["x_percent"] * screen_width)
                            y = int(data["y_percent"] * screen_height)
                            # Move mouse without any delay or pause
                            pyautogui.moveTo(x, y, duration=0, _pause=False)
                            
                        elif data["type"] == "click":
                            # Handle mouse clicks
                            if data["button"] == "Button.left":
                                if data["pressed"]:
                                    pyautogui.mouseDown(button="left")
                                else:
                                    pyautogui.mouseUp(button="left")
                            elif data["button"] == "Button.right":
                                if data["pressed"]:
                                    pyautogui.mouseDown(button="right")
                                else:
                                    pyautogui.mouseUp(button="right")
                        
                except json.JSONDecodeError:
                    print("Invalid data received")
                    self.buffer = ""  # Clear buffer on error
                    continue
                except Exception as e:
                    print(f"Error processing mouse event: {str(e)}")
                    break
                    
        except Exception as e:
            print(f"Failed to connect: {str(e)}")
        finally:
            self.client.close()

def main():
    # Create GUI for selection
    root = tk.Tk()
    root.title("Cross-Border Mouse Control")
    root.geometry("300x200")
    
    def start_server():
        root.destroy()
        server = MouseServer()
        server.start_server()
        
    def start_client():
        host = host_entry.get()
        root.destroy()
        client = MouseClient()
        client.connect_to_server(host)
    
    tk.Label(root, text="Choose Mode:", pady=10).pack()
    
    tk.Button(root, text="Start Server (Mac)", command=start_server).pack()
    
    tk.Label(root, text="Or enter server IP to connect:", pady=10).pack()
    host_entry = tk.Entry(root)
    host_entry.insert(0, "192.168.1.3")  # Prefill IP address
    host_entry.pack()
    tk.Button(root, text="Connect to Server (Windows)", command=start_client).pack()
    
    root.mainloop()

if __name__ == "__main__":
    main()
