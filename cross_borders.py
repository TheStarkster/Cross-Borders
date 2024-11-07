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
        self.remote_mode = False  # Added remote mode flag

    def start_server(self):
        try:
            self.server.bind((self.host, self.port))
            self.server.listen(1)
            self.is_running = True
            print(f"Server started on {self.host}:{self.port}")

            # Create GUI window
            self.root = tk.Tk()
            self.root.title("Cross-Border Mouse Control")
            self.root.geometry("300x200")  # Increased height

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

    def start_mouse_tracking(self):
        def on_move(x, y):
            if x <= 0:
                if not self.remote_mode:
                    self.remote_mode = True
                    print("Entered remote mode")
                    # Optionally keep cursor at the edge
                    pyautogui.moveTo(0, y, duration=0, _pause=False)
            else:
                if self.remote_mode:
                    self.remote_mode = False
                    print("Exited remote mode")
            if self.remote_mode and self.client and self.is_running:
                try:
                    # Get screen size
                    screen_width, screen_height = pyautogui.size()

                    # Convert coordinates to percentages
                    x_percent = x / screen_width
                    y_percent = y / screen_height

                    # Send move event
                    data = json.dumps({
                        'event': 'move',
                        'x_percent': x_percent,
                        'y_percent': y_percent
                    }) + '\n'  # Add newline as message delimiter
                    self.client.send(data.encode())
                except Exception as e:
                    print(f"Error sending move event: {str(e)}")

        def on_click(x, y, button, pressed):
            if self.remote_mode and self.client and self.is_running:
                try:
                    # Send click event
                    data = json.dumps({
                        'event': 'click',
                        'button': str(button),
                        'pressed': pressed
                    }) + '\n'
                    self.client.send(data.encode())
                except Exception as e:
                    print(f"Error sending click event: {str(e)}")

        # Stop existing listener if any
        if self.listener:
            self.listener.stop()

        # Start mouse listener
        self.listener = mouse.Listener(on_move=on_move, on_click=on_click)
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
                        event = data.get('event')

                        if event == 'move':
                            x_percent = data['x_percent']
                            y_percent = data['y_percent']
                            x = int(x_percent * screen_width)
                            y = int(y_percent * screen_height)
                            # Move mouse without any delay or pause
                            pyautogui.moveTo(x, y, duration=0, _pause=False)
                        elif event == 'click':
                            button = data['button']
                            pressed = data['pressed']
                            if button == 'Button.left':
                                button = 'left'
                            elif button == 'Button.right':
                                button = 'right'
                            else:
                                continue  # Unsupported button
                            if pressed:
                                pyautogui.mouseDown(button=button)
                            else:
                                pyautogui.mouseUp(button=button)

                except json.JSONDecodeError:
                    print("Invalid data received")
                    self.buffer = ""  # Clear buffer on error
                    continue
                except Exception as e:
                    print(f"Error processing event: {str(e)}")
                    break

        except Exception as e:
            print(f"Failed to connect: {str(e)}")
        finally:
            self.client.close()

def main():
    # Create GUI for selection
    root = tk.Tk()
    root.title("Cross-Border Mouse Control")
    root.geometry("300x200")  # Increased height

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
