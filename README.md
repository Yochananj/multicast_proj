# Multicast Screen Sharing

This project allows for screen sharing to multiple clients on a local network using multicast. It also includes features for remote control, such as freezing the client's keyboard and mouse, and even remotely shutting down or killing the client's machine.

## Features

*   **Screen Sharing:** Share your screen to multiple clients on the same network.
*   **Remote Control:**
    *   Freeze and unfreeze client's keyboard and mouse.
    *   Remotely shutdown the client's computer.
    *   Kill the client application.
*   **Secure:** Communication is encrypted using AES GCM.
*   **GUI:** A simple GUI to control the server.

## Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/yochananj/multicast_proj
    ```
2.  Navigate to the project directory:
    ```bash
    cd multicast_proj
    ```
3.  Create and activate a Virtual Environment:
    
    For Windows:
    ```powershell
    py -m venv .venv
    .venv\Scripts\activate
    ```
    
    For MacOS:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```
    
4.  Install the required packages (use `pip3` instead of `pip` for MacOS):
    ```bash
    pip install anyio flet opencv-python numpy cryptography mss pynput
    ```

## Usage

### Server

To start the server, run the `gui.py` file:
For Windows:
```powershell
py gui.py
```

For MacOS:
```bash
python3 gui.py
```
Enter a password in the GUI and click "confirm". This will start the server and begin announcing its presence on the network.

### Client

To start the client, run the `client.py` file:

For Windows:
```powershell
py client.py
```

For MacOS:
```bash
python3 client.py
```
The client will listen for server announcements and present you with a list of available servers. Choose a server and enter the password to start receiving the screen share.
