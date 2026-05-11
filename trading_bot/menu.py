#!/usr/bin/env python3
"""
Swing Trading Bot - Main Menu
==========================
Run: python3 menu.py
"""

import os
import sys
import subprocess
from datetime import datetime

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    clear_screen()
    print(f"{BLUE}{BOLD}")
    print("╔" + "═" * 58 + "╗")
    print("║" + " Swing Trading Bot ".center(58) + "║")
    print("║" + " Zerodha Kite Connect ".center(58) + "║")
    print("╚" + "═" * 58 + "╝")
    print(f"{RESET}")

def print_menu():
    print(f"\n{BOLD}MAIN MENU:{RESET}\n")
    print(f"  {GREEN}1.{RESET}  Start Live Trading")
    print(f"  {GREEN}2.{RESET}  Start Paper Trading")
    print(f"  {GREEN}3.{RESET}  Today's Backtest Scan")
    print(f"  {GREEN}4.{RESET}  View Logs (tail -f)")
    print(f"  {GREEN}5.{RESET}  Check Bot Status")
    print(f"  {RED}6.{RESET}  Stop Bot")
    print(f"  {GREEN}7.{RESET}  Git Pull & Update")
    print(f"  {RED}0.{RESET}  Exit")
    print()

def is_bot_running():
    try:
        result = subprocess.run(["pgrep", "-f", "python3 main.py"], 
                         capture_output=True, text=True)
        return bool(result.stdout.strip())
    except:
        return False

def get_bot_pid():
    try:
        result = subprocess.run(["pgrep", "-f", "python3 main.py"], 
                         capture_output=True, text=True)
        return result.stdout.strip().split('\n')[0] if result.stdout.strip() else None
    except:
        return None

def start_bot(mode="live"):
    if is_bot_running():
        print(f"\n{RED}Bot is already running!{RESET}")
        input(f"\n{YELLOW}Press Enter...{RESET}")
        return
    
    print(f"\n{GREEN}Starting bot in {mode} mode...{RESET}")
    os.environ["TRADING_MODE"] = mode
    
    with open("bot.log", "a") as f:
        subprocess.Popen(
            ["python3", "main.py"],
            stdout=f,
            stderr=subprocess.STDOUT,
            start_new_session=True
        )
    print(f"{GREEN}Bot started!{RESET}")
    input(f"\n{YELLOW}Press Enter...{RESET}")

def stop_bot():
    pid = get_bot_pid()
    if pid:
        try:
            subprocess.run(["kill", pid])
            print(f"{GREEN}Bot stopped!{RESET}")
        except:
            print(f"{RED}Failed to stop{RESET}")
    else:
        print(f"{YELLOW}Bot not running{RESET}")
    input(f"\n{YELLOW}Press Enter...{RESET}")

def view_logs():
    print(f"\n{YELLOW}Press Ctrl+C to exit{RESET}\n")
    try:
        subprocess.run(["tail", "-f", "bot.log"])
    except:
        subprocess.run(["tail", "20", "bot.log"])

def check_status():
    print()
    if is_bot_running():
        pid = get_bot_pid()
        print(f"{GREEN}● Bot RUNNING (PID: {pid}){RESET}")
        try:
            result = subprocess.run(["tail", "-10", "bot.log"], 
                               capture_output=True, text=True)
            if result.stdout:
                print(f"\n{YELLOW}Recent:{RESET}")
                print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)
        except:
            pass
    else:
        print(f"{RED}○ Bot STOPPED{RESET}")
    input(f"\n{YELLOW}Press Enter...{RESET}")

def run_backtest():
    print(f"\n{GREEN}Running backtest...{RESET}\n")
    try:
        subprocess.run(["python3", "today_backtest.py"])
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
    input(f"\n{YELLOW}Press Enter...{RESET}")

def git_pull():
    print(f"\n{GREEN}Pulling updates...{RESET}")
    try:
        result = subprocess.run(["git", "pull", "origin", "main"], 
                         capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print(f"{RED}{result.stderr}{RESET}")
    except Exception as e:
        print(f"{RED}Error: {e}{RESET}")
    input(f"\n{YELLOW}Press Enter...{RESET}")

def main():
    while True:
        print_header()
        print_menu()
        
        choice = input(f"{BOLD}Select:{RESET} ").strip()
        
        if choice == "1":
            start_bot("live")
        elif choice == "2":
            start_bot("paper")
        elif choice == "3":
            run_backtest()
        elif choice == "4":
            view_logs()
        elif choice == "5":
            check_status()
        elif choice == "6":
            stop_bot()
        elif choice == "7":
            git_pull()
        elif choice == "0":
            print(f"\n{GREEN}Bye!{RESET}\n")
            break
        else:
            print(f"{RED}Invalid{RESET}")

if __name__ == "__main__":
    main()