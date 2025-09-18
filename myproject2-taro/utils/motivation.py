# motivation.py
def get_motivation_text(rep_count: int) -> str:
    """
    Generate motivational messages based on current rep count.
    Cycles through predefined messages to encourage user progress.
    Returns "Ready to start!" for zero reps, otherwise formats with rep number.
    """
    
    motivational_messages = [
        "Yasss queen, slay it! 💃✨",
        "Work it, honeyyy! 🌈",
        "Slay đi em ơi! 🔥",
        "Cố lên diva ơi! 💖",
        "Shine bright, darling! ✨",
        "Beast mode on, baby! 🐯",
        "Push it, gorgeous! 😘",
        "Come throughhh, superstar! 🌟",
        "Ngầu quá trời, em ơi! 😍",
        "No pain, no glam, honey! 💎"
    ]

    if rep_count == 0:
        return "Ready to start!"
    
    # Cycle through messages based on rep count to maintain variety
    message_index = (rep_count - 1) % len(motivational_messages)
    selected_message = motivational_messages[message_index]
    
    return f"Rep {rep_count} - {selected_message}"