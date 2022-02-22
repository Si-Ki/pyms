#!/usr/bin/env python3
"""
pyms: A simple terminal based music player.
"""

import os
import sys
import signal
import random
import contextlib
import cursor
import time
from collections import defaultdict
from pynput import keyboard
with contextlib.redirect_stdout(None):
    import pygame
import threading
import mutagen

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

box_width = 46

polling_interval = 0.5

i_lines = [
    ("", True),
    ("░"*box_width, True),
    ("", True),
    ("00:00 " + " "*(box_width - 12) + " 00:00", True),
    ("", True),
    ("██████    ██  ██                ██      █ ████", True),
    ("██████    ██  ██    ██████    ██████      ██  ", True),
    ("██████    ██  ██                ██      ████ █", True),
    ("", True),
    ("escape    pause       F8        F9      pg_dwn", True)
]

play1 = "██▄▄  "  # i_lines[4][0][10:16]
play2 = "██████"  # i_lines[5][0][10:16]
play3 = "██▀▀  "  # i_lines[6][0][10:16]

paus1 = "██  ██"
paus2 = "██  ██"
paus3 = "██  ██"

m_file = ""


def exit_handler(signum, frame):
    """
    Executes whenever the signal SIGINT is received.

    Args:
        signum (int): The signal number.
        frame (frame): The frame.
    """
    exit_gracefully()


def resize_handler(signum, frame):
    """
    Executes whenever the size of the terminal is changed.
    Calls redraw() in execution to update the screen.

    Args:
        signum (int): The signal number.
        frame (frame): The frame.
    """
    redraw()


def exit_gracefully():
    """
    Executes whenever the signal SIGINT is received.

    Args:
        signum (int): The signal number.
        frame (frame): The frame.
    """
    pygame.mixer.music.stop()
    os.system("clear")
    cursor.show()
    os._exit(0)


def redraw():
    """
    Clears the screen and redraws the ui.
    """
    sys.stdout.flush()
    os.system("clear")
    sys.stdout.flush()
    print(interface(i_lines))
    sys.stdout.flush()


def pause_symbol():
    """
    Replaces the play symbol with the pause symbol.
    """
    line1 = i_lines[6][0][0:10] + paus1 + i_lines[6][0][16:]
    line2 = i_lines[7][0][0:10] + paus2 + i_lines[7][0][16:]
    line3 = i_lines[8][0][0:10] + paus3 + i_lines[8][0][16:]

    i_lines[6] = (line1, True)
    i_lines[7] = (line2, True)
    i_lines[8] = (line3, True)


def play_symbol():
    """
    Replaces the pause symbol with the play symbol.
    """
    line1 = i_lines[6][0][0:10] + play1 + i_lines[6][0][16:]
    line2 = i_lines[7][0][0:10] + play2 + i_lines[7][0][16:]
    line3 = i_lines[8][0][0:10] + play3 + i_lines[8][0][16:]

    i_lines[6] = (line1, True)
    i_lines[7] = (line2, True)
    i_lines[8] = (line3, True)


def strip_path_from_filename(path):
    """
    Removes the path from the filename.

    Args:
        path (str): Full path to the file.

    Returns:
        str: The filename without the path.
    """
    if "/" in path:
        filename = path.split("/")[-1]
        return filename
    return path


def strip_filename_from_path(path):
    """
    Removes the filename from the path.

    Args:
        path (str): Full path to the file.

    Returns:
        str: The path without the filename.
    """
    if "/" not in path:
        return os.getcwd()
    words = path.split("/")
    words = words[:-1]
    new_path = "/".join(words)
    return new_path + "/"


def random_file(path):
    """
    Returns a random file from the given path.

    Args:
        path (str): The path to the directory to search.

    Returns:
        str: A random file from the given path.
    """
    old_filename = strip_path_from_filename(path)
    stripped_path = strip_filename_from_path(path)

    # Consider only music files in the directory
    files = os.listdir(stripped_path)
    music_files = []
    for file in files:
        if (file.endswith(".mp3")
            or file.endswith(".wav")
            or file.endswith(".ogg")
            ) and file != old_filename:
            music_files.append(file)

    try:
        # Get a random file from the directory (do not repeat the original file)
        random_file = random.choice(music_files)
    except IndexError or ValueError:
        raise pygame.error("No music files found in the directory.")

    # Return the path to the new random file
    return os.path.join(stripped_path, random_file)


def interface(lines):
    """
    Creates a box of the terminal size, enclosing the lines
    passed in as a list of tuples.

    Args:
        lines (list): A list of tuples, each containing a line and a boolean.
        The line is the text to be displayed, and the boolean is whether
        the line should be centered.

    Returns:
        str: A string of the box with the lines fitted in.
    """
    global box_width

    size = os.get_terminal_size()
    width = size.columns
    height = size.lines
    string = "\n" * (int(height/2) - int(len(lines)/2))
    term = "..."

    # Create the body
    for tupl in lines:
        line = tupl[0]
        line_len = len(line)

        # Shorten the line if it is too long
        if line_len > min(box_width, width):
            line = line[:min(box_width, width) - len(term)] + term

        if tupl[1]:
            # Center the line
            formatted_line = line.center(min(box_width, width))

        else:
            # Left justify the line
            formatted_line = line.ljust(min(box_width, width))

        # Center the final line
        formatted_line = formatted_line.center(width)
        string += formatted_line + "\n"

    return string


def bar_parser(percentage, max_width):
    """
    Creates a bar of the given percentage.
    Args:
        percentage (float): The percentage of the bar to be filled.
        max_width (int): The maximum width of the bar.
    Returns:
        str: A string of the bar.
    """
    bar_width = int(percentage * max_width)
    bar = "█" * bar_width + "░" * (max_width - bar_width)

    return bar


def song_info_parser(current_secs, total_secs, volume, max_width):
    """
    Parses the current time and total time of the song,
    as well as the volume centered in the line.
    Args:
        current_secs (int): The current seconds of the song.
        total_secs (int): The total seconds of the song.
        volume (float): The volume of the song.
        max_width (int): The maximum width of the line.
    Returns:
        str: A string of the song info.
    """
    # Convert the seconds to minutes and seconds
    current_mins, current_secs = divmod(current_secs, 60)
    total_mins, total_secs = divmod(total_secs, 60)    

    # Convert the volume to a percentage
    volume = int(volume * 100)
    volume = volume + 1 if volume % 10 == 9 else volume

    # Format the time
    current_time = "{:02d}:{:02d}".format(current_mins, current_secs)
    total_time = "{:02d}:{:02d}".format(total_mins, total_secs)

    # Format the volume
    volume = "Volume: " + str(volume) + "%"

    # Format the final info string
    line = current_time + " / " + total_time + volume.rjust(max_width - len(current_time) - len(total_time) - 3)
    return line


def update_bar():

    global m_file, box_width

    # Load the audio file to mutagen
    audio = mutagen.File(m_file)

    # Obtain current and total times
    curr_time = int(pygame.mixer.music.get_pos() / 1000)
    total_time = int(audio.info.length)

    # Calculate the percentage of the song that is played
    percentage = curr_time / total_time

    # Get the progress bar
    progress_bar = bar_parser(percentage, box_width)
    return progress_bar


def update_song_info():

    global m_file, box_width

    # Load the audio file to mutagen
    audio = mutagen.File(m_file)

    # Obtain current and total times
    curr_time = int(pygame.mixer.music.get_pos() / 1000)
    total_time = int(audio.info.length)

    # Call song_info_parser to get the song info
    song_info = song_info_parser(curr_time, total_time, pygame.mixer.music.get_volume(), box_width)
    return song_info


def keyboard_listener():
    """
    Executes in a separate thread to capture pressed keys.
    Keeps that thread blocked until a key is pressed and then
    the key is captured and handled.
    """
    global i_lines, m_file

    press_or_release = defaultdict(lambda: 0)

    with keyboard.Events() as events:
        for event in events:

            # (Clear user input)
            print(" "*16 + "\r", end="")

            # (Check only for key presses)
            press_or_release[event.key] += 1
            if not press_or_release[event.key] % 2:
                continue

            # If the ESC key is pressed, exit
            if event.key == keyboard.Key.esc:
                exit_gracefully()

            # If the PAUSE key is pressed, play/pause
            elif event.key == keyboard.Key.pause:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.pause()
                    play_symbol()
                else:
                    pygame.mixer.music.unpause()
                    pause_symbol()
                redraw()

            # If the PAGE DOWN key is pressed, shuffle
            elif event.key == keyboard.Key.page_down:
                try:
                    # Get a random file, load it and play it
                    m_file = random_file(m_file)
                    pygame.mixer.music.load(m_file)
                    pygame.mixer.music.play()
                    
                    # Update the song title, info and bar and redraw
                    i_lines[0] = (strip_path_from_filename(m_file), False)
                    i_lines[2] = (update_bar(), True)
                    i_lines[4] = (update_song_info(), True)
                    pause_symbol()
                    redraw()

                except pygame.error:
                    # Rewind the current song if no random file is found
                    pygame.mixer.music.rewind()
                    if not pygame.mixer.music.get_busy():
                        pygame.mixer.music.unpause()
                        
                        # Update the song info and bar and redraw
                        i_lines[2] = (update_bar(), True)
                        i_lines[4] = (update_song_info(), True)
                        pause_symbol()
                        redraw()

            # If the F8 key is pressed, lower volume
            elif event.key == keyboard.Key.f8:
                curr_vol = pygame.mixer.music.get_volume()
                new_vol = round(round(curr_vol, 1), 8) - 0.10000000
                pygame.mixer.music.set_volume(new_vol)

                # Update the song info and redraw
                i_lines[4] = (update_song_info(), True)
                redraw()

            # If the F9 key is pressed, raise volume
            elif event.key == keyboard.Key.f9:
                curr_vol = pygame.mixer.music.get_volume()
                new_vol = round(round(curr_vol, 1), 8) + 0.10000000
                pygame.mixer.music.set_volume(new_vol)

                # Update the song info and redraw
                i_lines[4] = (update_song_info(), True)
                redraw()


def infinite_queue(event_type):
    """
    Captures a song end event and adds a new song to the queue.
    The new song is randomly selected from the directory and played.
    The thread is blocked waiting for the song to end and only then
    it unblocks and plays the next song so run all the threads 
    you would like to run before calling this function on the main thread.
    Args:
        event (pygame.event): The event that is captured. Usually MUSIC_END
    """
    global m_file

    while True:
        
        # When the song ends, play a new random song
        event = pygame.event.wait()
        if event.type == event_type:
            try:
            
                # Get a random file, load it and play it
                m_file = random_file(m_file)
                pygame.mixer.music.load(m_file)
                pygame.mixer.music.play()
                
                # Update title, bar and song info and redraw
                i_lines[0] = (strip_path_from_filename(m_file), False)
                i_lines[2] = (update_bar(), True)
                i_lines[4] = (update_song_info(), True)
                pause_symbol()
                redraw()

            except pygame.error:
                pass


def poll_interface(interval):
    """
    Updates the progress bar and the song time info every interval.
    The thread is blocked updating the bar until the song is finished.
    Args:
        interval (double): The interval in seconds between updates.
    """
    while True:
        
        time.sleep(interval)
        
        # Update bar and song info and redraw
        i_lines[2] = (update_bar(), True)
        i_lines[4] = (update_song_info(), True)
        redraw()


def main():

    global i_lines, m_file, box_width, polling_interval

    # Check input arguments
    if len(sys.argv) != 2:
        print("Usage: pyms <file>")
        exit(1)
    m_file = sys.argv[1]

    # If the path is a folder, get a random file from it
    if os.path.isdir(m_file):
        try:
            m_file = m_file + "/" if m_file[-1] != "/" else m_file
            m_file = random_file(m_file)
        except pygame.error:
            print("No music files found in the directory.")
            exit(1)

    # Initialize pygame mixer
    pygame.init()
    try:
        pygame.mixer.music.load(m_file)
        pygame.mixer.music.play()
    except pygame.error:
        print("Error: Could not load music file.")
        sys.exit(1)

    # Send an event when the song ends
    MUSIC_END = pygame.USEREVENT+1
    pygame.mixer.music.set_endevent(MUSIC_END)

    # Fancy interface magic
    cursor.hide()
    i_lines = [(strip_path_from_filename(m_file), False)] + i_lines
    redraw()
    signal.signal(signal.SIGWINCH, resize_handler)
    signal.signal(signal.SIGINT, exit_handler)

    # THRD1 - Initialize the keyboard listener
    th = threading.Thread(target=keyboard_listener)
    th.start()

    # THRD2 - Initialize the infinite queue
    th2 = threading.Thread(target=infinite_queue, args=(MUSIC_END,))
    th2.start()

    # MAIN - Dynamic progress bar
    poll_interface(polling_interval)


if __name__ == "__main__":
    main()
