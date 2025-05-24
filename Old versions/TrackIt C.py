import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
import csv
import os
import matplotlib.pyplot as plt
import sys

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # For PyInstaller
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

from collections import defaultdict

# ------------------------ Constants ------------------------
SUBJECTS = ["Math", "Physics", "Chemistry"]
CSV_FILE = resource_path("study_log.csv")
DEFAULT_DAILY_GOAL = 690

# ------------------------ CSV Logger ------------------------
class CSVLogger:
    def __init__(self, filename):
        self.filename = filename
        if not os.path.exists(self.filename):
            with open(self.filename, mode='w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["date", "subject", "minutes"])

    def log(self, subject, minutes):
        with open(self.filename, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([datetime.now().date(), subject, round(minutes, 2)])

    def get_today_minutes(self):
        today = datetime.now().date()
        total = 0
        with open(self.filename, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['date'] == str(today):
                    total += float(row['minutes'])
        return total

    def get_weekly_data(self):
        data = defaultdict(lambda: defaultdict(float))
        with open(self.filename, newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                date = row['date']
                subject = row['subject']
                minutes = float(row['minutes'])
                data[date][subject] += minutes
        return data

# ------------------------ Graph Plotter ------------------------
def plot_graph(data, daily_goal):
    dates = sorted(data.keys())[-7:]
    subjects = SUBJECTS

    subject_colors = {
        "Math": "#4e79a7",
        "Physics": "#f28e2b",
        "Chemistry": "#e15759",
    }

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

    fig, ax = plt.subplots(figsize=(10, 5))
    bottom = [0] * len(dates)
    for subj in subjects:
        ax.bar(dates, bars[subj], bottom=bottom, label=subj, color=subject_colors[subj])
        bottom = [sum(x) for x in zip(bottom, bars[subj])]

    ax.axhline(daily_goal, color='green', linestyle='--', label='Daily Goal')
    ax.axhline(weekly_avg, color='purple', linestyle=':', label=f'Weekly Avg: {int(weekly_avg // 60)} hr {int(weekly_avg % 60)} min')

    ax.set_title("Study Time - Last 7 Days")
    ax.set_ylabel("Study Duration")
    ax.set_yticks([i * 60 for i in range(0, 13, 2)] + [60, 180, 300, 420])
    ax.set_yticklabels([f"{i} hr" if i > 0 else "0" for i in range(0, 13, 2)] + ["", "", "", ""])
    ax.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

# ------------------------ Main App Class ------------------------
class StudyTrackerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TrackIt")
        self.logger = CSVLogger(CSV_FILE)
        self.is_dark = False

        self.daily_goal = DEFAULT_DAILY_GOAL

        # Timer state
        self.timer_running = False
        self.remaining_time = 0
        self.logged_time = 0

        self.build_ui()
        self.apply_theme()
        self.update_goal_progress()

    def build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure([i for i in range(8)], weight=1)

        top_frame = ttk.Frame(self.root)
        top_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=10)
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)

        self.title_label = ttk.Label(top_frame, text="TrackIt", font=("Helvetica", 26, "bold"))
        self.title_label.grid(row=0, column=0, sticky='w')

        self.theme_btn = ttk.Button(top_frame, text="Toggle Theme", command=self.toggle_theme)
        self.theme_btn.grid(row=0, column=1, sticky='e')
        self.theme_btn.configure(style="Theme.TButton")

        input_frame = ttk.Frame(self.root)
        input_frame.grid(row=1, column=0, pady=10, padx=10, sticky='n')
        input_frame.columnconfigure((0, 1), weight=1)

        self.subject_var = tk.StringVar()
        ttk.Label(input_frame, text="Subject:").grid(row=0, column=0, sticky='e')
        self.subject_menu = ttk.Combobox(input_frame, textvariable=self.subject_var, values=SUBJECTS, state='readonly')
        self.subject_menu.grid(row=0, column=1, sticky='ew', padx=5)

        self.duration_var = tk.StringVar()
        ttk.Label(input_frame, text="Session Duration (mins):").grid(row=1, column=0, sticky='e')
        self.duration_entry = ttk.Entry(input_frame, textvariable=self.duration_var)
        self.duration_entry.grid(row=1, column=1, sticky='ew', padx=5)

        self.goal_var = tk.StringVar()
        ttk.Label(input_frame, text="Daily Goal (mins):").grid(row=2, column=0, sticky='e')
        self.goal_entry = ttk.Entry(input_frame, textvariable=self.goal_var)
        self.goal_entry.grid(row=2, column=1, sticky='ew', padx=5)
        ttk.Button(input_frame, text="Set Goal", command=self.set_goal, style="Primary.TButton").grid(row=2, column=2, padx=5)

        self.timer_label = ttk.Label(self.root, text="00:00:00", font=("Helvetica", 24))
        self.timer_label.grid(row=2, column=0, pady=10)

        btn_frame = ttk.Frame(self.root)
        btn_frame.grid(row=3, column=0, pady=5)
        for i in range(4):
            btn_frame.columnconfigure(i, weight=1)

        self.start_pause_btn = ttk.Button(btn_frame, text="Start", command=self.toggle_timer, style="Primary.TButton")
        self.start_pause_btn.grid(row=0, column=0, padx=5)

        ttk.Button(btn_frame, text="Reset", command=self.reset_timer, style="Danger.TButton").grid(row=0, column=1, padx=5)

        ttk.Button(self.root, text="Log Session Now", command=self.manual_log, style="Accent.TButton").grid(row=4, column=0, pady=5)

        self.progress_var = tk.DoubleVar()
        self.progress_label = ttk.Label(self.root, text="")
        self.progress_label.grid(row=5, column=0)
        self.progress_bar = ttk.Progressbar(self.root, maximum=self.daily_goal, variable=self.progress_var)
        self.progress_bar.grid(row=6, column=0, sticky='ew', padx=10, pady=5)

        ttk.Button(self.root, text="Show Progress Graph", command=self.show_graph, style="Graph.TButton").grid(row=7, column=0, pady=10)

    def apply_theme(self):
        bg = "#1e1e1e" if self.is_dark else "#ffffff"
        fg = "#ffffff" if self.is_dark else "#000000"
        style = ttk.Style()
        style.theme_use('default')
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TFrame", background=bg)
        style.configure("TButton", padding=6)
        style.configure("Theme.TButton", background="#87ceeb")
        style.configure("Primary.TButton", background="#4CAF50")
        style.configure("Danger.TButton", background="#f44336")
        style.configure("Accent.TButton", background="#2196F3")
        style.configure("Graph.TButton", background="#9C27B0")
        self.root.configure(bg=bg)

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        self.apply_theme()

    def update_goal_progress(self):
        total = self.logger.get_today_minutes()
        self.progress_bar.config(maximum=self.daily_goal)
        self.progress_var.set(total)
        hrs = int(total // 60)
        mins = int(total % 60)
        goal_hrs = int(self.daily_goal // 60)
        goal_mins = int(self.daily_goal % 60)
        self.progress_label.config(text=f"Today: {hrs} hr {mins} min / {goal_hrs} hr {goal_mins} min")

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
                self.start_pause_btn.config(text="Pause")
                self.update_timer()
            except ValueError:
                messagebox.showerror("Invalid Input", "Enter a valid duration and select a subject.")
        else:
            elapsed_seconds = int(float(self.duration_var.get()) * 60) - self.remaining_time
            session_logged = (elapsed_seconds - self.logged_time) / 60
            if session_logged > 0:
                self.logger.log(self.subject_var.get(), session_logged)
                self.logged_time += elapsed_seconds - self.logged_time
                self.update_goal_progress()
                messagebox.showinfo("Session Paused", f"{int(session_logged)} minutes logged.")
            self.timer_running = False
            self.start_pause_btn.config(text="Start")

    def reset_timer(self):
        self.timer_running = False
        self.remaining_time = 0
        self.logged_time = 0
        self.timer_label.config(text="00:00:00")
        self.start_pause_btn.config(text="Start")

    def update_timer(self):
        if self.remaining_time <= 0:
            self.timer_label.config(text="00:00:00")
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
            self.start_pause_btn.config(text="Start")
            return

        mins, secs = divmod(self.remaining_time, 60)
        hours, mins = divmod(mins, 60)
        self.timer_label.config(text=f"{int(hours):02}:{int(mins):02}:{int(secs):02}")
        self.remaining_time -= 1
        if self.timer_running:
            self.root.after(1000, self.update_timer)

    def manual_log(self):
        try:
            mins = float(self.duration_var.get())
            if self.subject_var.get() == "":
                raise ValueError("Subject not selected")
            self.logger.log(self.subject_var.get(), mins)
            self.update_goal_progress()
            messagebox.showinfo("Session Logged", "Study session manually logged!")
        except ValueError:
            messagebox.showerror("Invalid Input", "Enter a valid duration and select a subject.")

    def show_graph(self):
        data = self.logger.get_weekly_data()
        plot_graph(data, self.daily_goal)

# ------------------------ Run App ------------------------
if __name__ == '__main__':
    root = tk.Tk()
    app = StudyTrackerApp(root)
    root.mainloop()
