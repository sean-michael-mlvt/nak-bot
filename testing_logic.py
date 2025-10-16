import sys
import asyncio
import argparse
from logic import check_correct

async def main():

    # Create parser for parsing arguments
    parser = argparse.ArgumentParser(description="Command-line tester for logic.py functions.")
    subparsers = parser.add_subparsers(dest='command', help='The function to test', required=True)

    # Parse arguments for testing the check_correct( ) command
    parser_check = subparsers.add_parser('check', help='Test the check_correct fuzzy matching function.')
    parser_check.add_argument('correct_answer', type=str, help='The correct answer string.')
    parser_check.add_argument('user_answer', type=str, help='The user-submitted answer string.')
    parser_check.add_argument('question_type', type=str, help='The type of the question (TF, QA, LQ)')
    parser_check.add_argument('difficulty', type=int, help='The difficulty of the question (1-5)')

    args = parser.parse_args()


    match args.command:
        case "check":
            is_correct, points = await check_correct(args.correct_answer, args.user_answer, args.question_type, args.difficulty)
            print("\n--- check_correct() Test ---")
            print(f"Points: {points}")
            print(f"Correct: {is_correct}")
            print("----------------------------\n")

if __name__ == "__main__":
    asyncio.run(main())