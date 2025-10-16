from thefuzz import fuzz
import math
import logging
import sys

DEBUG = False   # Toggles logging

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Determines correctness given the correct answer, user answer, and question type
async def check_correct(correct_answer: str, user_answer: str, question_type: str, difficulty: int):
    
    # Remove trailing whitespace and newline characters
    correct_answer = correct_answer.lower().strip()
    user_answer = user_answer.lower().strip()

    is_correct = False
    points_to_award, max_points = 0, difficulty * 10

    match question_type:
        # Question Answer
        case "QA":
            similarity_score = fuzz.ratio(correct_answer, user_answer)
            if DEBUG:
                logging.info(f"Similarity score between {correct_answer} and {user_answer} is {similarity_score}")
            if similarity_score >= 85:
                is_correct = True
                points_to_award = max_points
        # True False
        case "TF":
            if correct_answer[0] == user_answer[0]:
                is_correct = True
                points_to_award = max_points
        # List Question
        case "LQ":
            # Separate string answers into lists of answers
            correct_answers = [answer.strip() for answer in correct_answer.split(",")]
            user_answers = [answer.strip() for answer in user_answer.split(",")]

            # Create a mutable copy of correct answers to track matches
            available_correct_answers = list(correct_answers)

            points_per_answer = math.floor(max_points / len(correct_answers))
            matched_count = 0

            # If the user submits more answers than exist, award zero points.
            if len(user_answers) > len(correct_answers):
                return False, 0

            # For each submitted answer, find the best correct match
            for u_answer in user_answers:
                best_match_score = 0
                best_match_answer = None

                for c_answer in available_correct_answers:
                    score = fuzz.ratio(u_answer, c_answer)
                    if score > best_match_score:
                        best_match_score = score
                        best_match_answer = c_answer
                
                # If a sufficiently strong match is found, award points
                if best_match_score >= 85:
                    points_to_award += points_per_answer
                    matched_count += 1
                    # Remove the matched answer so it can't be used again
                    if best_match_answer:
                        available_correct_answers.remove(best_match_answer)
            
            # If the user got all answers correct, award full points
            if matched_count == len(correct_answers) and len(user_answers) == len(correct_answers):
                is_correct = True
                points_to_award = max_points # Ensure max points for a perfect score

    return is_correct, points_to_award
                    

            
            

    

