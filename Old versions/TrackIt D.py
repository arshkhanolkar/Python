import customtkinter as ctk
from tkinter import StringVar, DoubleVar
import tkinter.messagebox as messagebox
from datetime import datetime, timedelta
import csv
import os
import matplotlib
matplotlib.use('TkAgg')  # Set matplotlib backend
import matplotlib.pyplot as plt
import sys
import tempfile
import webbrowser
import json
from collections import defaultdict
from PIL import Image, ImageTk
import random
import subprocess
import logging
import numpy as np
from scipy.ndimage import gaussian_filter1d

# ======================= CONSTANTS =======================
# Set up basic logging
logging.basicConfig(filename='trackit_debug.log', level=logging.DEBUG)

# Color Palette
COLORS = {
    "primary": "#4B89DC",
    "secondary": "#6C757D",
    "success": "#4CAF50",
    "danger": "#F44336",
    "warning": "#FF9800",
    "purple": "#9C27B0",
    "teal": "#009688"
}

# Spacing
PAD_X = 16
PAD_Y = 16
SECTION_GAP = 24
BTN_HEIGHT = 40
BTN_PAD_X = 12
BTN_PAD_Y = 8

# Defaults
DEFAULT_SUBJECTS = ["Math", "Physics", "Chemistry"]
DEFAULT_DAILY_GOAL = 690  # 11.5 hours in minutes

def resource_path(relative_path):
    """Get the correct path for resources, whether running as script or compiled."""
    try:
        pass  # Add your code logic here
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base_path, relative_path)
    except Exception as e:
        logging.error(f"Error in resource_path: {str(e)}")
        return relative_path

CSV_FILE = resource_path("study_log.csv")
CONFIG_FILE = resource_path("config.json")

# ======================= FONTS (will be initialized after root creation) =======================
FONTS = None

# ======================= GRAPH UTILITIES =======================
def get_temp_graph_path():
    """Get a safe temp file path that works in installed apps"""
    try:
        temp_dir = tempfile.gettempdir()
        logging.info(f"Using temp directory: {temp_dir}")
        filename = f"trackit_graph_{random.randint(1000,9999)}.png"
        full_path = os.path.join(temp_dir, filename)
        logging.info(f"Generated graph path: {full_path}")
        return full_path
    except Exception as e:
        logging.error(f"Error in get_temp_graph_path: {str(e)}")
        return resource_path("temp_graph.png")

def cleanup_graph_files():
    """Clean up old graph files to prevent clutter"""
    try:
        temp_dir = tempfile.gettempdir()
        for file in os.listdir(temp_dir):
            if file.startswith("trackit_graph_") and file.endswith(".png"):
                try:
                    os.remove(os.path.join(temp_dir, file))
                except Exception as e:
                    logging.warning(f"Couldn't remove {file}: {str(e)}")
    except Exception as e:
        logging.error(f"Error in cleanup_graph_files: {str(e)}")

def show_graph_in_viewer(graph_path):
    """Universal graph display with multiple fallback methods"""
    try:
        if not os.path.exists(graph_path):
            raise FileNotFoundError(f"Graph file not found at {graph_path}")
        
        logging.info(f"Attempting to display graph: {graph_path}")
        
        # First try system-specific open commands
        try:
            if sys.platform == "win32":
                os.startfile(graph_path)
                logging.info("Opened with Windows startfile")
                return True
            elif sys.platform == "darwin":
                subprocess.run(["open", graph_path], check=True)
                logging.info("Opened with macOS open command")
                return True
            else:
                subprocess.run(["xdg-open", graph_path], check=True)
                logging.info("Opened with xdg-open")
                return True
        except Exception as sys_ex:
            logging.warning(f"System open failed, trying webbrowser: {str(sys_ex)}")
            
            # Fallback to webbrowser
            try:
                webbrowser.open(graph_path)
                logging.info("Opened with webbrowser")
                return True
            except Exception as web_ex:
                logging.warning(f"Webbrowser failed: {str(web_ex)}")
                
        # Final fallback to Tkinter viewer
        try:
            img_window = ctk.CTkToplevel()
            img_window.title("Study Graph")
            
            img = Image.open(graph_path)
            img = img.resize((800, 400), Image.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            # Keep reference to avoid garbage collection
            img_window._photo = photo
            
            label = ctk.CTkLabel(img_window, image=photo, text="")
            label.grid(row=0, column=0, padx=PAD_X, pady=PAD_Y)
            
            # Add close button
            close_btn = ctk.CTkButton(
                img_window, 
                text="Close", 
                command=img_window.destroy,
                fg_color=COLORS["secondary"],
                height=BTN_HEIGHT
            )
            close_btn.grid(row=1, column=0, pady=PAD_Y)
            
            logging.info("Opened with Tkinter viewer")
            return True
        except Exception as tk_ex:
            logging.error(f"Tkinter viewer failed: {str(tk_ex)}")
            raise tk_ex
            
    except Exception as e:
        error_msg = f"Couldn't open graph viewer. The graph was saved to:\n{graph_path}\nError: {str(e)}"
        logging.error(error_msg)
        messagebox.showerror("Graph Display Error", error_msg)
        return False

# ======================= GRAPH PLOTTING FUNCTIONS =======================
def plot_graph(data, daily_goal):
    try:
        if not data:
            messagebox.showerror("Error", "No study data available!")
            return False
        
        dates = sorted(data.keys())[-7:]
        if not dates:
            messagebox.showerror("Error", "No valid dates in data!")
            return False
            
        subjects = list(data[dates[0]].keys()) if dates else []

        color_palette = ["#4e79a7", "#f28e2b", "#e15759", "#76b7b2", "#59a14f", "#edc948", "#b07aa1"]
        subject_colors = {subj: color_palette[i % len(color_palette)] for i, subj in enumerate(subjects)}

        daily_totals = []
        bars = {subj: [] for subj in subjects}

        for date in dates:
            day_total = 0
            for subj in subjects:
                mins = data[date].get(subj, 0)
                bars[subj].append(mins)
                day_total += mins
            daily_totals.append(day_total)

        weekly_avg = sum(daily_totals) / len(dates) if dates else 0

        plt.figure(figsize=(10, 5))
        bottom = [0] * len(dates)
        for subj in subjects:
            plt.bar(dates, bars[subj], bottom=bottom, label=subj, color=subject_colors[subj])
            bottom = [sum(x) for x in zip(bottom, bars[subj])]

        plt.axhline(daily_goal, color='green', linestyle='--', label='Daily Goal')
        plt.axhline(weekly_avg, color='purple', linestyle=':', label=f'Weekly Avg: {int(weekly_avg//60)}h {int(weekly_avg%60)}m')
        plt.title("Study Time - Last 7 Days")
        plt.ylabel("Minutes")
        plt.xticks(rotation=45)
        plt.legend()
        plt.tight_layout()

        graph_path = get_temp_graph_path()
        plt.savefig(graph_path, bbox_inches='tight', dpi=100)
        plt.close()
        
        # Verify the file was created
        if not os.path.exists(graph_path):
            raise RuntimeError("Graph file was not created")
            
        return show_graph_in_viewer(graph_path)
    except Exception as e:
        messagebox.showerror("Graph Error", f"Error generating graph: {str(e)}")
        logging.error(f"Error in plot_graph: {str(e)}")
        return False

def plot_subject_distribution(data, daily_goal=None):
    try:
        subject_totals = defaultdict(float)
        for date, subjects in data.items():
            for subject, minutes in subjects.items():
                subject_totals[subject] += minutes
                
        if not subject_totals:
            messagebox.showerror("Error", "No subject data available!")
            return False
            
        plt.figure(figsize=(8, 8))
        plt.pie(subject_totals.values(), labels=subject_totals.keys(), 
               autopct='%1.1f%%', startangle=90)
        plt.title("Your Study Time by Subject")
        
        graph_path = get_temp_graph_path()
        plt.savefig(graph_path, bbox_inches='tight', dpi=100)
        plt.close()
        
        if not os.path.exists(graph_path):
            raise RuntimeError("Graph file was not created")
            
        return show_graph_in_viewer(graph_path)
    except Exception as e:
        messagebox.showerror("Graph Error", f"Error generating pie chart: {str(e)}")
        logging.error(f"Error in plot_subject_distribution: {str(e)}")
        return False

def plot_weekly_trend(data, daily_goal):
    try:
        dates = sorted(data.keys())[-7:]
        if not dates:
            messagebox.showerror("Error", "No data available!")
            return False
            
        daily_totals = [sum(subjects.values()) for date, subjects in data.items() 
                       if date in dates]
        
        plt.figure(figsize=(10, 5))
        plt.plot(dates, daily_totals, 'o-', color='#4e79a7', linewidth=2)
        if daily_goal:
            plt.axhline(daily_goal, color='red', linestyle='--', label='Daily Goal')
        plt.title("Your Weekly Study Trend")
        plt.ylabel("Minutes")
        plt.grid(True, alpha=0.3)
        
        graph_path = get_temp_graph_path()
        plt.savefig(graph_path, bbox_inches='tight', dpi=100)
        plt.close()
        
        if not os.path.exists(graph_path):
            raise RuntimeError("Graph file was not created")
            
        return show_graph_in_viewer(graph_path)
    except Exception as e:
        messagebox.showerror("Graph Error", f"Error generating trend graph: {str(e)}")
        logging.error(f"Error in plot_weekly_trend: {str(e)}")
        return False

def plot_subject_comparison(data, daily_goal=None):
    try:
        subject_totals = defaultdict(float)
        for date, subjects in data.items():
            for subject, minutes in subjects.items():
                subject_totals[subject] += minutes
        
        if not subject_totals:
            messagebox.showerror("Error", "No subject data available!")
            return False
        
        plt.figure(figsize=(10, 5))
        bars = plt.bar(subject_totals.keys(), subject_totals.values(), color='#76b7b2')
        plt.bar_label(bars)
        plt.title("Total Time Spent per Subject")
        plt.ylabel("Minutes")
        
        graph_path = get_temp_graph_path()
        plt.savefig(graph_path, bbox_inches='tight', dpi=100)
        plt.close()
        
        if not os.path.exists(graph_path):
            raise RuntimeError("Graph file was not created")
            
        return show_graph_in_viewer(graph_path)
    except Exception as e:
        messagebox.showerror("Graph Error", f"Error generating comparison graph: {str(e)}")
        logging.error(f"Error in plot_subject_comparison: {str(e)}")
        return False

def plot_time_of_day_analysis(data, daily_goal=None):
    try:
        # Extract hour from timestamps and aggregate by hour
        hour_counts = defaultdict(float)
        hour_sums = defaultdict(float)
        
        for date, subjects in data.items():
            for subject, details in subjects.items():
                if isinstance(details, dict) and 'time' in details:
                    try:
                        time_obj = datetime.strptime(details['time'], "%H:%M:%S").time()
                        hour = time_obj.hour
                        minutes = details['minutes']
                        hour_counts[hour] += minutes
                        hour_sums[hour] += 1
                    except:
                        continue
        
        if not hour_counts:
            messagebox.showerror("Error", "No time data available in logs!")
            return False
        
        # Calculate average minutes per hour
        hours = sorted(hour_counts.keys())
        avg_minutes = [hour_counts[h] / max(1, hour_sums[h]) for h in hours]
        
        # Smooth the data
        sigma = 1.0  # Smoothing factor
        smoothed = gaussian_filter1d(avg_minutes, sigma)
        
        plt.figure(figsize=(10, 5))
        plt.plot(hours, smoothed, 'o-', color='#4e79a7', linewidth=2)
        
        # Find peak and slump hours
        max_idx = np.argmax(smoothed)
        min_idx = np.argmin(smoothed)
        
        plt.axvline(x=hours[max_idx], color='green', linestyle='--', 
                   label=f'Peak: {hours[max_idx]}:00 ({smoothed[max_idx]:.1f} min avg)')
        plt.axvline(x=hours[min_idx], color='red', linestyle=':', 
                   label=f'Slump: {hours[min_idx]}:00 ({smoothed[min_idx]:.1f} min avg)')
        
        plt.title("Your Daily Study Pattern")
        plt.xlabel("Hour of Day")
        plt.ylabel("Average Minutes Spent Studying")
        plt.xticks(range(24))
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        graph_path = get_temp_graph_path()
        plt.savefig(graph_path, bbox_inches='tight', dpi=100)
        plt.close()
        
        if not os.path.exists(graph_path):
            raise RuntimeError("Graph file was not created")
            
        return show_graph_in_viewer(graph_path)
    except Exception as e:
        messagebox.showerror("Graph Error", f"Error generating time of day analysis: {str(e)}")
        logging.error(f"Error in plot_time_of_day_analysis: {str(e)}")
        return False

# ======================= CONFIG MANAGER =======================
class ConfigManager:
    def __init__(self):
        self.subjects = DEFAULT_SUBJECTS
        self.load_config()
        
    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    self.subjects = config.get('subjects', DEFAULT_SUBJECTS)
                    logging.info("Loaded config successfully")
        except Exception as e:
            logging.error(f"Error loading config: {str(e)}")
            self.subjects = DEFAULT_SUBJECTS
            
    def save_config(self, new_subjects):
        try:
            self.subjects = new_subjects
            with open(CONFIG_FILE, 'w') as f:
                json.dump({'subjects': self.subjects}, f)
            logging.info("Saved config successfully")
        except Exception as e:
            logging.error(f"Error saving config: {str(e)}")
            raise

# ======================= CSV LOGGER =======================
class CSVLogger:
    def __init__(self, filename):
        self.filename = filename
        try:
            if not os.path.exists(self.filename):
                with open(self.filename, mode='w', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow(["date", "subject", "minutes", "time"])
                logging.info(f"Created new CSV file at {self.filename}")
        except Exception as e:
            logging.error(f"Error initializing CSV file: {str(e)}")
            raise

    def log(self, subject, minutes):
        try:
            current_time = datetime.now().time().strftime("%H:%M:%S")
            with open(self.filename, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([datetime.now().date(), subject, round(minutes, 2), current_time])
            logging.info(f"Logged session: {subject} for {minutes} minutes at {current_time}")
        except Exception as e:
            logging.error(f"Error logging session: {str(e)}")
            raise

    def get_today_minutes(self):
        try:
            today = datetime.now().date()
            total = 0
            if os.path.exists(self.filename):
                with open(self.filename, newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['date'] == str(today):
                            total += float(row['minutes'])
            logging.info(f"Today's minutes: {total}")
            return total
        except Exception as e:
            logging.error(f"Error getting today's minutes: {str(e)}")
            return 0

    def get_weekly_data(self):
        data = defaultdict(lambda: defaultdict(dict))
        try:
            if os.path.exists(self.filename):
                with open(self.filename, newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        date = row['date']
                        subject = row['subject']
                        minutes = float(row['minutes'])
                        time = row.get('time', '00:00:00')  # Default time if not present
                        data[date][subject] = {
                            'minutes': minutes,
                            'time': time
                        }
            logging.info(f"Retrieved weekly data with {len(data)} entries")
            return data
        except Exception as e:
            logging.error(f"Error getting weekly data: {str(e)}")
            return defaultdict(lambda: defaultdict(dict))

# ======================= MAIN APP CLASS =======================
class StudyTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TrackIt")
        self.config = ConfigManager()
        self.logger = CSVLogger(CSV_FILE)
        
        # Initialize fonts after root creation
        global FONTS
        FONTS = {
            "title": ctk.CTkFont(size=24, weight="bold"),
            "heading": ctk.CTkFont(size=18, weight="bold"),
            "subheading": ctk.CTkFont(size=16, weight="bold"),
            "body": ctk.CTkFont(size=14),
            "small": ctk.CTkFont(size=12)
        }
        
        # Configure CustomTkinter appearance
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")
        
        # Add debug info
        logging.info(f"Starting TrackIt. Temp dir: {tempfile.gettempdir()}")
        logging.info(f"CSV path: {CSV_FILE}")
        logging.info(f"Config path: {CONFIG_FILE}")
        
        cleanup_graph_files()  # Clean up old graph files on startup
        
        # Timer state
        self.timer_running = False
        self.remaining_time = 0
        self.logged_time = 0
        self.daily_goal = DEFAULT_DAILY_GOAL
        
        # Window configuration
        self.root.minsize(800, 600)
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_propagate(False)
        
        # Main container - using grid consistently
        self.container = ctk.CTkFrame(root)
        self.container.grid(row=0, column=0, sticky="nsew")
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        
        # Page management
        self.pages = {}
        self.init_pages()
        self.show_page("MainPage")

    def create_section(self, parent, title: str = None) -> ctk.CTkFrame:
        """Creates a consistent section block using grid"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        if title:
            label = ctk.CTkLabel(
                frame, 
                text=title, 
                font=FONTS["subheading"]
            )
            label.grid(row=0, column=0, sticky="w", pady=(0, PAD_Y))
        return frame

    def create_button(self, parent, text: str, command, color: str = "primary") -> ctk.CTkButton:
        """Creates consistent buttons"""
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            fg_color=COLORS[color],
            hover_color=self.adjust_brightness(COLORS[color], -20),
            font=FONTS["body"],
            height=BTN_HEIGHT,
            corner_radius=8
        )

    def adjust_brightness(self, hex_color, factor):
        """Helper to adjust color brightness"""
        hex_color = hex_color.lstrip('#')
        rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        rgb = tuple(max(0, min(255, int(channel * (1 + factor/100)))) for channel in rgb)
        return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"

    def init_pages(self):
        # Main Page
        main_frame = ctk.CTkFrame(self.container)
        self.build_main_ui(main_frame)
        self.pages["MainPage"] = main_frame
        
        # Settings Page
        settings_frame = ctk.CTkFrame(self.container)
        self.build_settings_ui(settings_frame)
        self.pages["SettingsPage"] = settings_frame
        
        # Graphs Page
        graphs_frame = ctk.CTkFrame(self.container)
        self.build_graphs_ui(graphs_frame)
        self.pages["GraphsPage"] = graphs_frame

    def build_main_ui(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(1, weight=1)
        
        # Header Section - using grid
        header_frame = self.create_section(frame)
        header_frame.grid(row=0, column=0, sticky="ew", padx=PAD_X, pady=PAD_Y)
        header_frame.grid_columnconfigure(1, weight=1)
        
        self.title_label = ctk.CTkLabel(
            header_frame, 
            text="TrackIt", 
            font=FONTS["title"]
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        
        # Settings button
        self.settings_btn = ctk.CTkButton(
            header_frame,
            text="⚙",
            width=40,
            height=40,
            corner_radius=20,
            fg_color="transparent",
            hover_color=("gray80", "gray20"),
            command=lambda: self.show_page("SettingsPage"),
            font=FONTS["subheading"]
        )
        self.settings_btn.grid(row=0, column=1, sticky="e")
        
        # Input Section - using grid
        input_section = self.create_section(frame, "Study Session")
        input_section.grid(row=1, column=0, sticky="nsew", padx=PAD_X, pady=(0, PAD_Y))
        input_section.grid_columnconfigure(1, weight=1)
        input_section.grid_columnconfigure(1, weight=1)
        
        # Subject input
        self.subject_var = ctk.StringVar()
        ctk.CTkLabel(
            input_section, 
            text="Subject:", 
            font=FONTS["body"]
        ).grid(row=1, column=0, sticky="e", padx=PAD_X, pady=PAD_Y)
        
        self.subject_menu = ctk.CTkComboBox(
            input_section,
            variable=self.subject_var,
            values=self.config.subjects,
            dropdown_fg_color=("gray90", "gray10"),
            button_color=("gray75", "gray25"),
            font=FONTS["body"]
        )
        self.subject_menu.grid(row=1, column=1, sticky="ew", padx=PAD_X, pady=PAD_Y)
        
        # Duration input
        self.duration_var = ctk.StringVar()
        ctk.CTkLabel(
            input_section, 
            text="Duration (mins):", 
            font=FONTS["body"]
        ).grid(row=2, column=0, sticky="e", padx=PAD_X, pady=PAD_Y)
        
        self.duration_entry = ctk.CTkEntry(
            input_section, 
            textvariable=self.duration_var,
            font=FONTS["body"]
        )
        self.duration_entry.grid(row=2, column=1, sticky="ew", padx=PAD_X, pady=PAD_Y)
        
        # Goal Section - using grid
        goal_section = self.create_section(frame, "Daily Goal")
        goal_section.grid(row=2, column=0, sticky="ew", padx=PAD_X, pady=(0, PAD_Y))
        goal_section.grid_columnconfigure(1, weight=1)
        
        self.goal_var = ctk.StringVar(value=str(DEFAULT_DAILY_GOAL))
        ctk.CTkLabel(
            goal_section, 
            text="Goal (mins):", 
            font=FONTS["body"]
        ).grid(row=1, column=0, sticky="e", padx=PAD_X, pady=PAD_Y)
        
        self.goal_entry = ctk.CTkEntry(
            goal_section, 
            textvariable=self.goal_var,
            font=FONTS["body"]
        )
        self.goal_entry.grid(row=1, column=1, sticky="ew", padx=PAD_X, pady=PAD_Y)
        
        self.create_button(
            goal_section, 
            "Set Goal", 
            self.set_goal, 
            "success"
        ).grid(row=1, column=2, padx=PAD_X, pady=PAD_Y)
        
        # Timer Display
        self.timer_label = ctk.CTkLabel(
            frame, 
            text="00:00:00", 
            font=ctk.CTkFont(size=32, weight="bold")
        )
        self.timer_label.grid(row=3, column=0, pady=SECTION_GAP)
        
        # Timer Controls - using grid
        btn_frame = self.create_section(frame)
        btn_frame.grid(row=4, column=0, pady=(0, SECTION_GAP))
        
        self.start_pause_btn = self.create_button(
            btn_frame, 
            "Start", 
            self.toggle_timer, 
            "primary"
        )
        self.start_pause_btn.grid(row=0, column=0, padx=PAD_X)
        
        self.create_button(
            btn_frame, 
            "Reset", 
            self.reset_timer, 
            "danger"
        ).grid(row=0, column=1, padx=PAD_X)
        
        # Manual Log Button
        self.create_button(
            frame, 
            "Log Session Now", 
            self.manual_log, 
            "primary"
        ).grid(row=5, column=0, pady=(0, SECTION_GAP))
        
        # Progress Tracking - using grid
        progress_section = self.create_section(frame)
        progress_section.grid(row=6, column=0, sticky="ew", padx=PAD_X, pady=(0, SECTION_GAP))
        
        self.progress_var = ctk.DoubleVar()
        self.progress_label = ctk.CTkLabel(
            progress_section, 
            text="", 
            font=FONTS["body"]
        )
        self.progress_label.grid(row=0, column=0)
        
        self.progress_bar = ctk.CTkProgressBar(
            progress_section, 
            orientation="horizontal",
            progress_color=COLORS["primary"]
        )
        self.progress_bar.grid(row=1, column=0, sticky="ew", pady=(PAD_Y, 0))
        
        # Graph Buttons - using grid
        self.create_button(
            frame, 
            "Quick Graph", 
            self.show_graph, 
            "purple"
        ).grid(row=7, column=0, pady=(0, PAD_Y))
        
        self.create_button(
            frame, 
            "More Visualizations →", 
            lambda: self.show_page("GraphsPage"), 
            "primary"
        ).grid(row=8, column=0, pady=(0, SECTION_GAP))
        
        # Initialize progress display
        self.update_goal_progress()

    def build_graphs_ui(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(2, weight=1)
        
        # Back button - using grid
        self.create_button(
            frame, 
            "← Back to Main", 
            lambda: self.show_page("MainPage"), 
            "success"
        ).grid(row=0, column=0, sticky="nw", padx=PAD_X, pady=PAD_Y)
        
        # Title - using grid
        ctk.CTkLabel(
            frame, 
            text="Study Visualizations", 
            font=FONTS["title"]
        ).grid(row=1, column=0, pady=SECTION_GAP)
        
        # Graph options frame - using grid
        options_frame = self.create_section(frame)
        options_frame.grid(row=2, column=0, sticky="nsew", padx=PAD_X, pady=(0, SECTION_GAP))
        options_frame.grid_columnconfigure(0, weight=1)
        
        # Graph options - using grid
        graph_options = [
            ("Weekly Overview", "Daily breakdown by subject", plot_graph),
            ("Subject Distribution", "See which subjects get most attention", plot_subject_distribution),
            ("Weekly Trend", "Compare days and spot patterns", plot_weekly_trend),
            ("Subject Comparison", "Total minutes spent per subject", plot_subject_comparison),
            ("Time of Day Analysis", "See when you're most productive", plot_time_of_day_analysis)
        ]
        
        for i, (title, desc, func) in enumerate(graph_options):
            btn = self.create_button(
                options_frame,
                title,
                lambda f=func: f(self.logger.get_weekly_data(), self.daily_goal),
                "purple"
            )
            btn.grid(row=i, column=0, pady=PAD_Y, padx=PAD_X, sticky='ew')
            
            ctk.CTkLabel(
                options_frame,
                text=desc,
                font=FONTS["small"],
                wraplength=400
            ).grid(row=i, column=1, sticky='w', padx=PAD_X)

    def build_settings_ui(self, frame):
        frame.grid_columnconfigure(0, weight=1)
        frame.grid_rowconfigure(3, weight=1)
        
        # Back button - using grid
        self.create_button(
            frame, 
            "← Back", 
            lambda: self.show_page("MainPage"), 
            "success"
        ).grid(row=0, column=0, sticky="nw", padx=PAD_X, pady=PAD_Y)
        
        # Theme toggle - using grid
        theme_frame = self.create_section(frame, "Appearance")
        theme_frame.grid(row=1, column=0, sticky="ew", padx=PAD_X, pady=(0, PAD_Y))
        
        self.theme_var = ctk.StringVar(value=ctk.get_appearance_mode().lower())
        self.theme_switch = ctk.CTkSwitch(
            theme_frame,
            text="Dark Mode",
            variable=self.theme_var,
            onvalue="dark",
            offvalue="light",
            command=self.toggle_theme,
            font=FONTS["body"]
        )
        self.theme_switch.grid(row=0, column=0, padx=PAD_X, pady=PAD_Y)
        
        # Set initial state
        current_mode = ctk.get_appearance_mode().lower()
        self.theme_var.set(current_mode)
        self.theme_switch.select() if current_mode == "dark" else self.theme_switch.deselect()
        
        # Subjects customization - using grid
        subjects_frame = self.create_section(frame, "Customize Subjects")
        subjects_frame.grid(row=2, column=0, sticky="ew", padx=PAD_X, pady=(0, PAD_Y))
        
        self.subjects_text = ctk.CTkTextbox(
            subjects_frame, 
            height=160, 
            width=300,
            font=FONTS["body"]
        )
        self.subjects_text.grid(row=0, column=0, padx=PAD_X, pady=PAD_Y, sticky="ew")
        subjects_frame.grid_columnconfigure(0, weight=1)
        self.subjects_text.insert("1.0", "\n".join(self.config.subjects))
        
        ctk.CTkLabel(
            subjects_frame, 
            text="Enter one subject per line", 
            font=FONTS["small"]
        ).grid(row=1, column=0)
        
        self.create_button(
            subjects_frame, 
            "Save Subjects", 
            self.save_subjects, 
            "success"
        ).grid(row=2, column=0, pady=SECTION_GAP)
        
        # Bottom padding
        ctk.CTkLabel(frame, text="").grid(row=3, column=0)

    def show_page(self, page_name):
        if hasattr(self, 'current_page'):
            self.current_page.grid_forget()
        self.current_page = self.pages[page_name]
        self.current_page.grid(row=0, column=0, sticky="nsew")
        self.current_page.tkraise()

    def save_subjects(self):
        text = self.subjects_text.get("1.0", "end-1c")
        new_subjects = [s.strip() for s in text.split("\n") if s.strip()]
        if new_subjects:
            try:
                self.config.save_config(new_subjects)
                self.subject_menu.configure(values=new_subjects)
                messagebox.showinfo("Success", "Subjects updated!")
                self.show_page("MainPage")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save subjects: {str(e)}")
        else:
            messagebox.showerror("Error", "Please enter at least one subject")

    def toggle_theme(self):
        new_mode = self.theme_var.get()
        ctk.set_appearance_mode(new_mode)
        logging.info(f"Changed theme to {new_mode}")

    def update_goal_progress(self):
        total = self.logger.get_today_minutes()
        self.progress_bar.set(total / self.daily_goal if self.daily_goal > 0 else 0)
        hrs = int(total // 60)
        mins = int(total % 60)
        goal_hrs = int(self.daily_goal // 60)
        goal_mins = int(self.daily_goal % 60)
        self.progress_label.configure(
            text=f"Today: {hrs} hr {mins} min / {goal_hrs} hr {goal_mins} min",
            font=FONTS["body"]
        )

    def set_goal(self):
        try:
            new_goal = int(self.goal_var.get())
            if new_goal <= 0:
                raise ValueError
            self.daily_goal = new_goal
            self.update_goal_progress()
            messagebox.showinfo("Goal Updated", f"Daily goal set to {new_goal} minutes.")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for daily goal.")

    def toggle_timer(self):
        if not self.timer_running:
            try:
                mins = float(self.duration_var.get())
                if self.subject_var.get() == "":
                    raise ValueError("Subject not selected")
                self.remaining_time = int(mins * 60)
                self.logged_time = 0
                self.timer_running = True
                self.start_pause_btn
            except ValueError as e:
                messagebox.showerror("Input Error", str(e))
            except Exception as e:
                logging.error(f"Unexpected error: {str(e)}")
                messagebox.showerror("Error", "An unexpected error occurred.")