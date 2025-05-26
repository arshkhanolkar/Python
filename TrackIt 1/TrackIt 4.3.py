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
import logging.handlers
import base64
import tempfile


# ======================= CONSTANTS =======================
# Set up basic logging
log_handler = logging.handlers.RotatingFileHandler(
    'trackit_debug.log', maxBytes=1*1024*1024, backupCount=3
)
logging.basicConfig(handlers=[log_handler], level=logging.DEBUG)

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
        if not os.access(temp_dir, os.W_OK):
            raise PermissionError(f"Temp directory not writable: {temp_dir}")
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

def plot_time_of_day_productivity(data, daily_mode=False):
    try:
        time_slots = defaultdict(int)
        session_counts = defaultdict(int)
        
        if not data:
            messagebox.showerror("Error", "No study data available!")
            return False
            
        if daily_mode:
            # For single day view, get the most recent day
            date = sorted(data.keys())[-1]
            day_data = {date: data[date]}
        else:
            # For multi-day view, aggregate all days
            day_data = data
            
        for date, subjects in day_data.items():
            try:
                with open(CSV_FILE, newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row['date'] == date:
                            time_str = row['timestamp']
                            hour = int(time_str.split(':')[0])
                            time_slot = f"{hour:02d}:00-{hour+1:02d}:00"
                            minutes = float(row['minutes'])
                            time_slots[time_slot] += minutes
                            session_counts[time_slot] += 1
            except Exception as e:
                logging.error(f"Error processing CSV for {date}: {str(e)}")
                continue
                
        if not time_slots:
            messagebox.showerror("Error", "No time data available!")
            return False
            
        time_labels = sorted(time_slots.keys())
        minutes_data = [time_slots[slot] for slot in time_labels]
        sessions_data = [session_counts[slot] for slot in time_labels]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))
        
        # Plot total minutes
        ax1.bar(time_labels, minutes_data, color='#4e79a7')
        ax1.set_title("Time-of-Day Productivity" + (" (Today)" if daily_mode else ""))
        ax1.set_ylabel("Total Minutes")
        ax1.tick_params(axis='x', rotation=45)
        
        # Plot session count
        ax2.bar(time_labels, sessions_data, color='#f28e2b')
        ax2.set_ylabel("Session Count")
        ax2.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()

        graph_path = get_temp_graph_path()
        plt.savefig(graph_path, bbox_inches='tight', dpi=100)
        plt.close()
        
        if not os.path.exists(graph_path):
            raise RuntimeError("Graph file was not created")
            
        return show_graph_in_viewer(graph_path)
    except Exception as e:
        messagebox.showerror("Graph Error", f"Error generating time-of-day graph: {str(e)}")
        logging.error(f"Error in plot_time_of_day_productivity: {str(e)}")
        return False
def plot_hourly_productivity_multiline(data):
    try:
        from matplotlib import pyplot as plt
        from datetime import datetime, timedelta

        last_7_dates = sorted(data.keys())[-7:]
        hourly_by_day = {date: [0] * 24 for date in last_7_dates}
        hourly_totals = [0] * 24

        with open(CSV_FILE, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date = row['date']
                if date not in last_7_dates:
                    continue
                try:
                    start_time = datetime.strptime(f"{row['date']} {row['timestamp']}", "%Y-%m-%d %H:%M:%S")
                    duration = timedelta(minutes=float(row['minutes']))
                    end_time = start_time + duration
                    current = start_time

                    while current < end_time:
                        hour = current.hour
                        next_hour = (current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
                        slice_end = min(end_time, next_hour)
                        minutes_in_hour = (slice_end - current).total_seconds() / 60

                        hourly_by_day[date][hour] += minutes_in_hour
                        current = slice_end
                except Exception as e:
                    logging.error(f"Error parsing session: {str(e)}")
                    continue

        for h in range(24):
            total = sum(hourly_by_day[day][h] for day in last_7_dates)
            hourly_totals[h] = total / len(last_7_dates) if last_7_dates else 0

        plt.figure(figsize=(12, 6))
        color_map = plt.get_cmap("tab10")

        for i, date in enumerate(last_7_dates):
            values = hourly_by_day.get(date, [0] * 24)
            plt.plot(range(24), values, label=date, color=color_map(i % 10), marker='o')

        plt.plot(range(24), hourly_totals, label='7-Day Avg', color='black', linestyle='--', linewidth=2)
        plt.xticks(range(24), [f"{h:02d}:00" for h in range(24)], rotation=45)
        plt.xlabel("Hour of Day")
        plt.ylabel("Minutes Studied")
        plt.title("Hourly Productivity — Last 7 Days (Smoothed)")
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.tight_layout()

        graph_path = get_temp_graph_path()
        plt.savefig(graph_path, bbox_inches='tight', dpi=100)
        plt.close()
        return show_graph_in_viewer(graph_path)

    except Exception as e:
        messagebox.showerror("Graph Error", f"Hourly productivity (multi-line) failed: {str(e)}")
        logging.error(f"plot_hourly_productivity_multiline error: {str(e)}")
        return False


# ======================= CONFIG MANAGER =======================
class ConfigManager:
    def __init__(self):
        self.subjects = DEFAULT_SUBJECTS
        self.daily_goal = DEFAULT_DAILY_GOAL
        self.theme = "system"  # default to system if not specified
        self.load_config()
        
    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = json.load(f)
                    if not isinstance(config, dict):
                        raise ValueError("Config file is not a valid dictionary")
                    self.subjects = config.get('subjects', DEFAULT_SUBJECTS)
                    self.daily_goal = config.get('daily_goal', DEFAULT_DAILY_GOAL)
                    self.theme = config.get('theme', 'system')  # load theme if exists
                    logging.info("Loaded config successfully")
        except Exception as e:
            logging.error(f"Error loading config: {str(e)} — resetting to defaults")
            self.subjects = DEFAULT_SUBJECTS
            self.daily_goal = DEFAULT_DAILY_GOAL
            self.theme = "system"
           
    def save_config(self, new_subjects=None, new_daily_goal=None, new_theme=None):
        try:
            # Load current values
            current_subjects = self.subjects
            current_goal = self.daily_goal
            current_theme = self.theme

            # Update if new values provided
            if new_subjects is not None:
                current_subjects = new_subjects
                self.subjects = new_subjects
            if new_daily_goal is not None:
                current_goal = new_daily_goal
                self.daily_goal = new_daily_goal
            if new_theme is not None:
                current_theme = new_theme
                self.theme = new_theme

            # Save all into the file
            with open(CONFIG_FILE, 'w') as f:
                json.dump({
                    'subjects': current_subjects,
                    'daily_goal': current_goal,
                    'theme': current_theme
                }, f)
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
                    writer.writerow(["date", "timestamp", "subject", "minutes"])
                logging.info(f"Created new CSV file at {self.filename}")
        except Exception as e:
            logging.error(f"Error initializing CSV file: {str(e)}")
            raise

    def log(self, subject, minutes):
        try:
            now = datetime.now()
            with open(self.filename, mode='a', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    now.date(),
                    now.strftime("%H:%M:%S"),
                    subject,
                    round(minutes, 2)
                ])
            logging.info(f"Logged session: {subject} for {minutes} minutes at {now}")
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
                            try:
                                total += float(row['minutes'])
                            except (ValueError, KeyError) as e:
                                logging.warning(f"Skipping invalid row in get_today_minutes: {row} — {str(e)}")
                                continue
            logging.info(f"Today's minutes: {total}")
            return total
        except Exception as e:
            logging.error(f"Error getting today's minutes: {str(e)}")
            return 0

    def get_weekly_data(self):
        data = defaultdict(lambda: defaultdict(float))
        try:
            if os.path.exists(self.filename):
                with open(self.filename, newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            date = row['date']
                            subject = row['subject']
                            minutes = float(row['minutes'])
                            data[date][subject] += minutes
                        except (ValueError, KeyError) as e:
                            logging.warning(f"Skipping invalid row in get_weekly_data: {row} — {str(e)}")
                            continue
            logging.info(f"Retrieved weekly data with {len(data)} entries")
            return data
        except Exception as e:
            logging.error(f"Error getting weekly data: {str(e)}")
            return defaultdict(lambda: defaultdict(float))

    def get_all_data(self):
        data = defaultdict(lambda: defaultdict(float))
        try:
            if os.path.exists(self.filename):
                with open(self.filename, newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        try:
                            date = row['date']
                            subject = row['subject']
                            minutes = float(row['minutes'])
                            data[date][subject] += minutes
                        except (ValueError, KeyError) as e:
                            logging.warning(f"Skipping invalid row in get_all_data: {row} — {str(e)}")
                            continue
            logging.info(f"Retrieved all data with {len(data)} entries")
            return data
        except Exception as e:
            logging.error(f"Error getting all data: {str(e)}")
            return defaultdict(lambda: defaultdict(float))

# ======================= MAIN APP CLASS =======================
class StudyTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TrackIt")
        self.config = ConfigManager()
        self.logger = CSVLogger(CSV_FILE)
        self.daily_goal = self.config.daily_goal
        
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
        saved_theme = self.config.theme
        if saved_theme in ["light", "dark"]:
            ctk.set_appearance_mode(saved_theme)
        else:
            ctk.set_appearance_mode("system")
        # Set icon on settings button according to saved theme
    
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
        # Set the icon based on saved theme
        saved_theme = self.config.theme
        self.settings_btn.configure(text="☀️" if saved_theme == "light" else "🌙")

        
        
        # Input Section - using grid
        input_section = self.create_section(frame, "Study Session")
        input_section.grid(row=1, column=0, sticky="nsew", padx=PAD_X, pady=(0, PAD_Y))
        input_section.grid_columnconfigure(1, weight=1)
        input_section.grid_columnconfigure(1, weight=1)
        input_section.grid_rowconfigure(1, weight=1)
        input_section.grid_rowconfigure(2, weight=1)

        
        # Subject input
        self.subject_var = ctk.StringVar()
        ctk.CTkLabel(
            input_section, 
            text="Subject:", 
            font=FONTS["body"],
            width=80
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
        self.subject_menu.configure(width=150)
        
        # Duration input
        self.duration_var = ctk.StringVar()
        ctk.CTkLabel(
            input_section, 
            text="Duration (mins):", 
            font=FONTS["body"],
            width=80
        ).grid(row=2, column=0, sticky="e", padx=PAD_X, pady=PAD_Y)
        
        self.duration_entry = ctk.CTkEntry(
            input_section, 
            textvariable=self.duration_var,
            font=FONTS["body"]
        )
        self.duration_entry.grid(row=2, column=1, sticky="ew", padx=PAD_X, pady=PAD_Y)
        self.duration_entry.configure(width=150)
        
        # Goal Section - using grid
        goal_section = self.create_section(frame, "Daily Goal")
        goal_section.grid(row=2, column=0, sticky="ew", padx=PAD_X, pady=(0, PAD_Y))
        goal_section.grid_columnconfigure(1, weight=1)
        
        self.goal_var = ctk.StringVar(value=str(self.daily_goal))
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
        options_frame = ctk.CTkScrollableFrame(frame)
        options_frame.grid(row=2, column=0, sticky="nsew", padx=PAD_X, pady=(0, SECTION_GAP))
        options_frame.grid_columnconfigure(0, weight=1)
        
        # Graph options - using grid
        graph_options = [
            ("Weekly Overview", "Daily breakdown by subject", plot_graph),
            ("Subject Distribution", "See which subjects get most attention", plot_subject_distribution),
            ("Weekly Trend", "Compare days and spot patterns", plot_weekly_trend),
            ("Subject Comparison", "Total minutes spent per subject", plot_subject_comparison),
            ("Daily Productivity", "Your productivity by time of day (today)", 
             lambda: plot_time_of_day_productivity(self.logger.get_weekly_data(), daily_mode=True)),
            ("Overall Productivity", "Your productivity by time of day (all time)", 
             lambda: plot_time_of_day_productivity(self.logger.get_all_data(), daily_mode=False)), 
            ("Hourly Productivity (7 Days)", "Compare your productivity hour-by-hour across last 7 days", 
             lambda: plot_hourly_productivity_multiline(self.logger.get_weekly_data())),
 
 
        ]
        
        for i, (title, desc, func) in enumerate(graph_options):
            if i <= 3:
                def make_command(f):
                    return lambda: f(self.logger.get_weekly_data(), self.daily_goal)
                command = make_command(func)
            else:
                command = func
            btn = self.create_button(
                options_frame,
                title,
                command,
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
        self.create_button(
            frame, 
            "Toggle Dark/Light Mode", 
            self.toggle_theme,
            "warning"
        ).grid(row=1, column=0, pady=SECTION_GAP, padx=PAD_X)
        
        # Subjects customization - using grid
        subjects_frame = self.create_section(frame)
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
        new_subjects = []
        for s in text.split("\n"):
            s_clean = s.strip()
            if s_clean:
                #if not s_clean.isalnum():
                    #messagebox.showerror("Invalid Subject", f"Subject '{s_clean}' must be alphanumeric.")
                    #eturn
                new_subjects.append(s_clean)
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
        # Read the last saved theme
        current_mode = self.config.theme

        # If it's system, assume dark (fallback)
        if current_mode not in ["light", "dark"]:
            current_mode = "dark"

        # Flip the mode
        new_mode = "light" if current_mode == "dark" else "dark"
        ctk.set_appearance_mode(new_mode)

        # Save only light/dark (never system) into config
        self.config.save_config(
            new_subjects=self.config.subjects,
            new_daily_goal=self.config.daily_goal,
            new_theme=new_mode
        )
        logging.info(f"Theme toggled to {new_mode} and saved to config")

        # Update the settings button icon
        self.settings_btn.configure(text="☀️" if new_mode == "light" else "🌙")

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
            if new_goal > 1440:  # Clamp to max 24 hours/day
                new_goal = 1440
            self.daily_goal = new_goal
            self.update_goal_progress()
            messagebox.showinfo("Goal Updated", f"Daily goal set to {new_goal} minutes.")
            self.config.daily_goal = self.daily_goal
            self.config.save_config(self.config.subjects, self.daily_goal)

        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid number for daily goal.")

    def toggle_timer(self):
        if not self.timer_running:
            # Only set remaining_time if not already set (fresh start, not resume)
            if self.remaining_time <= 0:
                try:
                    mins = float(self.duration_var.get())
                    if not self.subject_var.get():
                        raise ValueError("Subject not selected")
                    self.remaining_time = int(mins * 60)
                    self.logged_time = 0
                except ValueError:
                    messagebox.showerror("Invalid Input", "Enter a valid duration and select a subject.")
                    return
            self.timer_running = True
            self.start_pause_btn.configure(text="Pause")
            self.update_timer()
        else:
            # Calculate how much time has elapsed since start
            total_seconds_set = int(float(self.duration_var.get()) * 60)
            elapsed_seconds = total_seconds_set - self.remaining_time

            # Only log if there’s new time since last log
            new_session_seconds = elapsed_seconds - self.logged_time
            session_minutes = new_session_seconds / 60

            if session_minutes > 0.1:
                subject = self.subject_var.get()
                self.logger.log(subject, session_minutes)
                self.logged_time += new_session_seconds
                self.update_goal_progress()
                messagebox.showinfo("Session Paused", f"{int(session_minutes)} minutes logged.")

            self.timer_running = False
            self.start_pause_btn.configure(text="Start")


    def reset_timer(self):
        self.duration_var.set("")
        self.subject_var.set("")
        self.timer_running = False
        self.remaining_time = 0
        self.logged_time = 0
        self.timer_label.configure(text="00:00:00")
        self.start_pause_btn.configure(text="Start")

    def update_timer(self):
        if self.remaining_time <= 0:
            self.timer_label.configure(text="00:00:00")
            if self.timer_running:
                try:
                    total_duration = float(self.duration_var.get())
                    subject = self.subject_var.get()
                    if subject:
                        self.logger.log(subject, total_duration)
                        self.update_goal_progress()
                        messagebox.showinfo("Session Complete", f"{int(total_duration)} minutes logged.")
                except ValueError:
                    pass
            self.timer_running = False
            self.start_pause_btn.configure(text="Start")
            return

        mins, secs = divmod(self.remaining_time, 60)
        hours, mins = divmod(mins, 60)
        self.timer_label.configure(text=f"{int(hours):02}:{int(mins):02}:{int(secs):02}")
        self.remaining_time -= 1
        if self.timer_running:
            self.root.after(1000, self.update_timer)

    
    def manual_log(self):
        try:
            mins = float(self.duration_var.get())
            if mins <= 0:
                raise ValueError("Duration must be positive")
            if mins > 1440: 
                mins = 1440
            if self.subject_var.get() == "":
                raise ValueError("Subject not selected")
            if not self.subject_var.get().strip().isalnum():
                raise ValueError("Subject name must be alphanumeric")
            self.logger.log(self.subject_var.get(), mins)
            self.update_goal_progress()
            messagebox.showinfo("Session Logged", "Study session manually logged!")
        except ValueError:
            messagebox.showerror("Invalid Input", "Enter a valid duration and select a subject.")

    def show_graph(self):
        data = self.logger.get_weekly_data()
        if not data:
            messagebox.showwarning("No Data", "No study sessions recorded yet!")
            return
        plot_graph(data, self.daily_goal)
# ======================= RUN APP =======================
if __name__ == '__main__':
    try:
        root = ctk.CTk()
        # Set the application icon
        # Embedded icon data (base64-encoded)
        icon_data = b"""
        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
        """

        # Decode and write to a temporary .ico file
        icon_bytes = base64.b64decode(icon_data)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ico") as tmp_icon:
            tmp_icon.write(icon_bytes)
            icon_path = tmp_icon.name

        root.iconbitmap(icon_path)

        
        # Initialize fonts after root creation
        FONTS = {
            "title": ctk.CTkFont(size=24, weight="bold"),
            "heading": ctk.CTkFont(size=18, weight="bold"),
            "subheading": ctk.CTkFont(size=16, weight="bold"),
            "body": ctk.CTkFont(size=14),
            "small": ctk.CTkFont(size=12)
        }
        app = StudyTrackerApp(root)
        root.mainloop()
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        messagebox.showerror("Fatal Error", f"The application encountered an error:\n{str(e)}\n\nCheck trackit_debug.log for details.")         
               