import sys
import os
import customtkinter as ctk
from ui.main_window import MainWindow

def main():
    """
    Keypoint: Application entry point for Aurras - Sound & Voice Studio.
    
    Controller: Sets global CustomTkinter appearance settings, 
    instantiates the main application window, and starts the event loop.
    """
    # Set up global UI theme and appearance mode
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("dark-blue")
    
    # Initialize and run the main application frame
    app = MainWindow()
    app.mainloop()

if __name__ == "__main__":
    main()