import socket
import pyautogui
import json
import threading
import tkinter as tk
from tkinter import messagebox
from pynput import mouse, keyboard

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
        self.receive_thread = None
        self.keyboard_listener = None

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
            screen_width, screen_height = pyautogui.size()
            if x <= 0:
                if not self.remote_mode:
                    self.remote_mode = True
                    print("Entered remote mode")
                    # Optionally keep cursor at the edge
                    pyautogui.moveTo(0, y, duration=0, _pause=False)
            if self.remote_mode and self.client and self.is_running:
                try:
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
            elif not self.remote_mode and self.client and self.is_running:
                # Do nothing when not in remote mode
                pass

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

        # Start keyboard listener
        self.keyboard_listener = keyboard.Listener(on_press=self.on_key_press, on_release=self.on_key_release)
        self.keyboard_listener.start()

        # Start thread to receive messages from client
        self.receive_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.receive_thread.start()

    def on_key_press(self, key):
        if self.remote_mode and self.client and self.is_running:
            try:
                data = json.dumps({
                    'event': 'key',
                    'key': self.key_to_string(key),
                    'pressed': True
                }) + '\n'
                self.client.send(data.encode())
            except Exception as e:
                print(f"Error sending key press: {str(e)}")

    def on_key_release(self, key):
        if self.remote_mode and self.client and self.is_running:
            try:
                data = json.dumps({
                    'event': 'key',
                    'key': self.key_to_string(key),
                    'pressed': False
                }) + '\n'
                self.client.send(data.encode())
            except Exception as e:
                print(f"Error sending key release: {str(e)}")

    def key_to_string(self, key):
        if isinstance(key, keyboard.KeyCode):
            return key.char
        else:
            return str(key)

    def receive_messages(self):
        while self.is_running and self.client:
            try:
                data = self.client.recv(1024).decode()
                if not data:
                    break

                messages = data.strip().split('\n')
                for message in messages:
                    event = json.loads(message)
                    event_type = event.get('event')
                    if event_type == 'return_to_mac':
                        # Exit remote mode
                        self.remote_mode = False
                        print("Returned to Mac control")
                        # Optionally move cursor to the edge
                        x, y = pyautogui.position()
                        pyautogui.moveTo(1, y, duration=0, _pause=False)
            except Exception as e:
                print(f"Error receiving message from client: {str(e)}")
                break

    def stop_server(self):
        self.is_running = False
        if self.listener:
            self.listener.stop()
        if self.keyboard_listener:
            self.keyboard_listener.stop()
        if self.client:
            self.client.close()
        self.server.close()
        self.root.quit()

class MouseClient:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buffer = ""
        self.is_running = True
        self.send_thread = None
        self.keyboard_controller = keyboard.Controller()

    def connect_to_server(self, host):
        try:
            self.client.connect((host, 12345))
            print("Connected to server")

            # Start thread to send events to server
            self.start_sending_events()

            # Get screen size once
            screen_width, screen_height = pyautogui.size()

            while self.is_running:
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
                        elif event == 'key':
                            key = data['key']
                            pressed = data['pressed']
                            try:
                                if len(key) == 1:
                                    # Regular character
                                    if pressed:
                                        self.keyboard_controller.press(key)
                                    else:
                                        self.keyboard_controller.release(key)
                                else:
                                    # Special key
                                    key_obj = self.string_to_key(key)
                                    if key_obj:
                                        if pressed:
                                            self.keyboard_controller.press(key_obj)
                                        else:
                                            self.keyboard_controller.release(key_obj)
                            except Exception as e:
                                print(f"Error simulating key event: {str(e)}")
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
            self.is_running = False
            self.client.close()

    def start_sending_events(self):
        self.send_thread = threading.Thread(target=self.send_events, daemon=True)
        self.send_thread.start()

    def send_events(self):
        screen_width, screen_height = pyautogui.size()

        def on_move(x, y):
            if not self.is_running:
                return
            try:
                if x >= screen_width - 1:
                    # Send message to server to return control to Mac
                    data = json.dumps({'event': 'return_to_mac'}) + '\n'
                    self.client.send(data.encode())
                    print("Sent return_to_mac event")
                    # Optionally keep cursor at the edge
                    pyautogui.moveTo(screen_width - 1, y, duration=0, _pause=False)
            except Exception as e:
                print(f"Error sending event to server: {str(e)}")

        # Start mouse listener
        self.mouse_listener = mouse.Listener(on_move=on_move)
        self.mouse_listener.start()

    def string_to_key(self, key_str):
        key_mapping = {
            'Key.space': keyboard.Key.space,
            'Key.enter': keyboard.Key.enter,
            'Key.shift': keyboard.Key.shift,
            'Key.shift_r': keyboard.Key.shift_r,
            'Key.ctrl_l': keyboard.Key.ctrl_l,
            'Key.ctrl_r': keyboard.Key.ctrl_r,
            'Key.alt_l': keyboard.Key.alt_l,
            'Key.alt_r': keyboard.Key.alt_r,
            'Key.tab': keyboard.Key.tab,
            'Key.backspace': keyboard.Key.backspace,
            'Key.esc': keyboard.Key.esc,
            'Key.up': keyboard.Key.up,
            'Key.down': keyboard.Key.down,
            'Key.left': keyboard.Key.left,
            'Key.right': keyboard.Key.right,
            # Add other keys as needed
        }
        return key_mapping.get(key_str, None)

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
