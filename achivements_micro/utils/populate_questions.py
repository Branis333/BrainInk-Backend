import sys
import os
# Add the parent directory to the path so we can import from the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session, sessionmaker
from db.connection import engine
from models.question_bank import QuestionBank

def populate_question_bank():
    """Populate the question bank with diverse questions (overwrite existing)"""
    
    questions = [
        # MATHEMATICS - Elementary
        {
            "question_text": "What is 15 + 27?",
            "option_a": "42",
            "option_b": "41", 
            "option_c": "43",
            "option_d": "40",
            "correct_answer": "A",
            "subject": "Mathematics",
            "topic": "Basic Addition",
            "difficulty_level": "elementary",
            "explanation": "15 + 27 = 42"
        },
        {
            "question_text": "What is 8 × 7?",
            "option_a": "54",
            "option_b": "56",
            "option_c": "58", 
            "option_d": "52",
            "correct_answer": "B",
            "subject": "Mathematics",
            "topic": "Multiplication",
            "difficulty_level": "elementary",
            "explanation": "8 × 7 = 56"
        },
        {
            "question_text": "What is the area of a rectangle with length 6 and width 4?",
            "option_a": "20",
            "option_b": "22",
            "option_c": "24",
            "option_d": "26",
            "correct_answer": "C",
            "subject": "Mathematics",
            "topic": "Geometry",
            "difficulty_level": "middle_school",
            "explanation": "Area = length × width = 6 × 4 = 24"
        },
        {
            "question_text": "What is the value of x in the equation 2x + 5 = 15?",
            "option_a": "5",
            "option_b": "6",
            "option_c": "4",
            "option_d": "7",
            "correct_answer": "A",
            "subject": "Mathematics", 
            "topic": "Algebra",
            "difficulty_level": "high_school",
            "explanation": "2x + 5 = 15, so 2x = 10, therefore x = 5"
        },
        {
            "question_text": "What is the derivative of x²?",
            "option_a": "x",
            "option_b": "2x",
            "option_c": "x²",
            "option_d": "2x²",
            "correct_answer": "B",
            "subject": "Mathematics",
            "topic": "Calculus",
            "difficulty_level": "university",
            "explanation": "The derivative of x² is 2x using the power rule"
        },
        
        # SCIENCE - Physics
        {
            "question_text": "What is the formula for force?",
            "option_a": "F = ma",
            "option_b": "F = mv",
            "option_c": "F = mg",
            "option_d": "F = mc²",
            "correct_answer": "A",
            "subject": "Science",
            "topic": "Physics",
            "difficulty_level": "high_school",
            "explanation": "Newton's second law states F = ma (Force = mass × acceleration)"
        },
        {
            "question_text": "What is the speed of light in vacuum?",
            "option_a": "3 × 10⁸ m/s",
            "option_b": "3 × 10⁹ m/s",
            "option_c": "3 × 10⁷ m/s",
            "option_d": "3 × 10¹⁰ m/s",
            "correct_answer": "A",
            "subject": "Science",
            "topic": "Physics",
            "difficulty_level": "high_school",
            "explanation": "The speed of light in vacuum is approximately 3 × 10⁸ meters per second"
        },
        {
            "question_text": "What is the unit of electric current?",
            "option_a": "Volt",
            "option_b": "Ampere",
            "option_c": "Ohm",
            "option_d": "Watt",
            "correct_answer": "B",
            "subject": "Science",
            "topic": "Physics",
            "difficulty_level": "middle_school",
            "explanation": "The Ampere (A) is the SI unit of electric current"
        },
        
        # SCIENCE - Chemistry
        {
            "question_text": "What is the chemical symbol for gold?",
            "option_a": "Go",
            "option_b": "Au",
            "option_c": "Ag", 
            "option_d": "Gd",
            "correct_answer": "B",
            "subject": "Science",
            "topic": "Chemistry",
            "difficulty_level": "middle_school",
            "explanation": "Au comes from the Latin word 'aurum' meaning gold"
        },
        {
            "question_text": "How many protons does carbon have?",
            "option_a": "4",
            "option_b": "5",
            "option_c": "6",
            "option_d": "7",
            "correct_answer": "C",
            "subject": "Science",
            "topic": "Chemistry",
            "difficulty_level": "high_school",
            "explanation": "Carbon has atomic number 6, meaning it has 6 protons"
        },
        {
            "question_text": "What is the molecular formula for water?",
            "option_a": "H2O",
            "option_b": "HO2",
            "option_c": "H3O",
            "option_d": "H2O2",
            "correct_answer": "A",
            "subject": "Science",
            "topic": "Chemistry",
            "difficulty_level": "elementary",
            "explanation": "Water consists of 2 hydrogen atoms and 1 oxygen atom: H2O"
        },
        
        # SCIENCE - Biology
        {
            "question_text": "How many chambers does a human heart have?",
            "option_a": "2",
            "option_b": "3",
            "option_c": "4",
            "option_d": "5",
            "correct_answer": "C",
            "subject": "Science",
            "topic": "Biology",
            "difficulty_level": "middle_school",
            "explanation": "The human heart has 4 chambers: 2 atria and 2 ventricles"
        },
        {
            "question_text": "What is the powerhouse of the cell?",
            "option_a": "Nucleus",
            "option_b": "Mitochondria",
            "option_c": "Ribosome",
            "option_d": "Chloroplast",
            "correct_answer": "B",
            "subject": "Science",
            "topic": "Biology",
            "difficulty_level": "high_school",
            "explanation": "Mitochondria produce ATP (energy) for the cell"
        },
        {
            "question_text": "What is the study of heredity called?",
            "option_a": "Genetics",
            "option_b": "Ecology",
            "option_c": "Anatomy",
            "option_d": "Physiology",
            "correct_answer": "A",
            "subject": "Science",
            "topic": "Biology",
            "difficulty_level": "high_school",
            "explanation": "Genetics is the study of genes and heredity"
        },
        
        # HISTORY - World History
        {
            "question_text": "In which year did World War II end?",
            "option_a": "1944",
            "option_b": "1945",
            "option_c": "1946",
            "option_d": "1947",
            "correct_answer": "B",
            "subject": "History",
            "topic": "World War II",
            "difficulty_level": "high_school",
            "explanation": "World War II ended in 1945 with Japan's surrender"
        },
        {
            "question_text": "Who was the first person to walk on the moon?",
            "option_a": "Buzz Aldrin",
            "option_b": "Neil Armstrong",
            "option_c": "John Glenn",
            "option_d": "Yuri Gagarin",
            "correct_answer": "B",
            "subject": "History",
            "topic": "Space Exploration",
            "difficulty_level": "middle_school",
            "explanation": "Neil Armstrong was the first person to walk on the moon on July 20, 1969"
        },
        {
            "question_text": "Which empire was ruled by Julius Caesar?",
            "option_a": "Greek Empire",
            "option_b": "Roman Empire", 
            "option_c": "Byzantine Empire",
            "option_d": "Persian Empire",
            "correct_answer": "B",
            "subject": "History",
            "topic": "Ancient Rome",
            "difficulty_level": "middle_school",
            "explanation": "Julius Caesar was a Roman general and statesman who ruled the Roman Empire"
        },
        {
            "question_text": "What year did the Berlin Wall fall?",
            "option_a": "1987",
            "option_b": "1988",
            "option_c": "1989",
            "option_d": "1990",
            "correct_answer": "C",
            "subject": "History",
            "topic": "Cold War",
            "difficulty_level": "high_school",
            "explanation": "The Berlin Wall fell on November 9, 1989"
        },
        
        # GEOGRAPHY
        {
            "question_text": "What is the capital of Australia?",
            "option_a": "Sydney",
            "option_b": "Melbourne",
            "option_c": "Canberra",
            "option_d": "Brisbane",
            "correct_answer": "C",
            "subject": "Geography",
            "topic": "World Capitals",
            "difficulty_level": "middle_school",
            "explanation": "Canberra is the capital city of Australia"
        },
        {
            "question_text": "Which is the longest river in the world?",
            "option_a": "Amazon River",
            "option_b": "Nile River",
            "option_c": "Mississippi River",
            "option_d": "Yangtze River",
            "correct_answer": "B",
            "subject": "Geography",
            "topic": "Rivers",
            "difficulty_level": "middle_school",
            "explanation": "The Nile River is the longest river in the world at 6,650 km"
        },
        {
            "question_text": "How many continents are there?",
            "option_a": "5",
            "option_b": "6",
            "option_c": "7",
            "option_d": "8",
            "correct_answer": "C",
            "subject": "Geography",
            "topic": "Continents",
            "difficulty_level": "elementary",
            "explanation": "There are 7 continents: Asia, Africa, North America, South America, Antarctica, Europe, and Australia"
        },
        {
            "question_text": "What is the smallest country in the world?",
            "option_a": "Monaco",
            "option_b": "Vatican City",
            "option_c": "San Marino",
            "option_d": "Liechtenstein",
            "correct_answer": "B",
            "subject": "Geography",
            "topic": "Countries",
            "difficulty_level": "high_school",
            "explanation": "Vatican City is the smallest country with an area of 0.17 square miles"
        },
        
        # LITERATURE
        {
            "question_text": "Who wrote 'Romeo and Juliet'?",
            "option_a": "Charles Dickens",
            "option_b": "William Shakespeare",
            "option_c": "Jane Austen",
            "option_d": "Mark Twain",
            "correct_answer": "B",
            "subject": "Literature",
            "topic": "Classic Literature",
            "difficulty_level": "middle_school",
            "explanation": "William Shakespeare wrote the tragedy Romeo and Juliet"
        },
        {
            "question_text": "In which book would you find the character Harry Potter?",
            "option_a": "Lord of the Rings",
            "option_b": "Chronicles of Narnia",
            "option_c": "Harry Potter series",
            "option_d": "Percy Jackson",
            "correct_answer": "C",
            "subject": "Literature",
            "topic": "Modern Literature",
            "difficulty_level": "elementary",
            "explanation": "Harry Potter is the main character in J.K. Rowling's Harry Potter series"
        },
        {
            "question_text": "Who wrote '1984'?",
            "option_a": "George Orwell",
            "option_b": "Aldous Huxley",
            "option_c": "Ray Bradbury",
            "option_d": "H.G. Wells",
            "correct_answer": "A",
            "subject": "Literature",
            "topic": "Dystopian Literature",
            "difficulty_level": "high_school",
            "explanation": "George Orwell wrote the dystopian novel '1984'"
        },
        
        # COMPUTER SCIENCE
        {
            "question_text": "What does HTML stand for?",
            "option_a": "Hyper Text Markup Language",
            "option_b": "High Tech Modern Language",
            "option_c": "Home Tool Markup Language",
            "option_d": "Hyperlink and Text Markup Language",
            "correct_answer": "A",
            "subject": "Computer Science",
            "topic": "Web Development",
            "difficulty_level": "high_school",
            "explanation": "HTML stands for Hyper Text Markup Language"
        },
        {
            "question_text": "Which programming language is known as the 'language of the web'?",
            "option_a": "Python",
            "option_b": "Java",
            "option_c": "JavaScript",
            "option_d": "C++",
            "correct_answer": "C",
            "subject": "Computer Science",
            "topic": "Programming Languages",
            "difficulty_level": "high_school",
            "explanation": "JavaScript is often called the language of the web"
        },
        {
            "question_text": "What does CPU stand for?",
            "option_a": "Computer Processing Unit",
            "option_b": "Central Processing Unit",
            "option_c": "Core Processing Unit",
            "option_d": "Central Program Unit",
            "correct_answer": "B",
            "subject": "Computer Science",
            "topic": "Computer Hardware",
            "difficulty_level": "middle_school",
            "explanation": "CPU stands for Central Processing Unit"
        },
        
        # ART & CULTURE
        {
            "question_text": "Who painted the Mona Lisa?",
            "option_a": "Vincent van Gogh",
            "option_b": "Pablo Picasso",
            "option_c": "Leonardo da Vinci",
            "option_d": "Michelangelo",
            "correct_answer": "C",
            "subject": "Art",
            "topic": "Renaissance Art",
            "difficulty_level": "middle_school",
            "explanation": "Leonardo da Vinci painted the Mona Lisa around 1503-1519"
        },
        {
            "question_text": "Which instrument has 88 keys?",
            "option_a": "Guitar",
            "option_b": "Piano",
            "option_c": "Violin",
            "option_d": "Flute",
            "correct_answer": "B",
            "subject": "Music",
            "topic": "Musical Instruments",
            "difficulty_level": "elementary",
            "explanation": "A standard piano has 88 keys (52 white and 36 black)"
        },
        {
            "question_text": "What is the art of beautiful handwriting called?",
            "option_a": "Typography",
            "option_b": "Calligraphy",
            "option_c": "Lithography",
            "option_d": "Photography",
            "correct_answer": "B",
            "subject": "Art",
            "topic": "Visual Arts",
            "difficulty_level": "middle_school",
            "explanation": "Calligraphy is the art of beautiful handwriting"
        },
        
        # SPORTS
        {
            "question_text": "How many players are on a basketball team on the court at one time?",
            "option_a": "4",
            "option_b": "5",
            "option_c": "6",
            "option_d": "7",
            "correct_answer": "B",
            "subject": "Sports",
            "topic": "Basketball",
            "difficulty_level": "elementary",
            "explanation": "There are 5 players per team on a basketball court at one time"
        },
        {
            "question_text": "In which sport would you perform a slam dunk?",
            "option_a": "Volleyball",
            "option_b": "Tennis",
            "option_c": "Basketball",
            "option_d": "Soccer",
            "correct_answer": "C",
            "subject": "Sports",
            "topic": "Basketball",
            "difficulty_level": "elementary",
            "explanation": "A slam dunk is a basketball move where a player jumps and puts the ball through the hoop"
        },
        {
            "question_text": "How often are the Summer Olympics held?",
            "option_a": "Every 2 years",
            "option_b": "Every 3 years",
            "option_c": "Every 4 years",
            "option_d": "Every 5 years",
            "correct_answer": "C",
            "subject": "Sports",
            "topic": "Olympics",
            "difficulty_level": "middle_school",
            "explanation": "The Summer Olympics are held every 4 years"
        },
        
        # ADDITIONAL MATH QUESTIONS
        {
            "question_text": "What is 12% of 200?",
            "option_a": "20",
            "option_b": "22",
            "option_c": "24",
            "option_d": "26",
            "correct_answer": "C",
            "subject": "Mathematics",
            "topic": "Percentages",
            "difficulty_level": "middle_school",
            "explanation": "12% of 200 = 0.12 × 200 = 24"
        },
        {
            "question_text": "What is the circumference of a circle with radius 5? (Use π ≈ 3.14)",
            "option_a": "31.4",
            "option_b": "15.7",
            "option_c": "28.26",
            "option_d": "78.5",
            "correct_answer": "A",
            "subject": "Mathematics",
            "topic": "Geometry",
            "difficulty_level": "high_school",
            "explanation": "Circumference = 2πr = 2 × 3.14 × 5 = 31.4"
        },
        {
            "question_text": "If a triangle has angles of 60° and 70°, what is the third angle?",
            "option_a": "40°",
            "option_b": "50°",
            "option_c": "60°",
            "option_d": "70°",
            "correct_answer": "B",
            "subject": "Mathematics",
            "topic": "Geometry",
            "difficulty_level": "middle_school",
            "explanation": "The sum of angles in a triangle is 180°. So 180° - 60° - 70° = 50°"
        },
        
        # ADDITIONAL SCIENCE QUESTIONS
        {
            "question_text": "What gas do plants absorb from the atmosphere during photosynthesis?",
            "option_a": "Oxygen",
            "option_b": "Nitrogen",
            "option_c": "Carbon Dioxide",
            "option_d": "Hydrogen",
            "correct_answer": "C",
            "subject": "Science",
            "topic": "Biology",
            "difficulty_level": "middle_school",
            "explanation": "Plants absorb carbon dioxide during photosynthesis and release oxygen"
        },
        {
            "question_text": "At what temperature does water boil at sea level?",
            "option_a": "90°C",
            "option_b": "95°C",
            "option_c": "100°C",
            "option_d": "105°C",
            "correct_answer": "C",
            "subject": "Science",
            "topic": "Physics",
            "difficulty_level": "elementary",
            "explanation": "Water boils at 100°C (212°F) at sea level"
        },
        {
            "question_text": "What is the hardest natural substance?",
            "option_a": "Gold",
            "option_b": "Iron",
            "option_c": "Diamond",
            "option_d": "Quartz",
            "correct_answer": "C",
            "subject": "Science",
            "topic": "Chemistry",
            "difficulty_level": "middle_school",
            "explanation": "Diamond is the hardest naturally occurring substance"
        },
        
        # ADDITIONAL HISTORY QUESTIONS
        {
            "question_text": "Who was the first President of the United States?",
            "option_a": "Thomas Jefferson",
            "option_b": "John Adams",
            "option_c": "George Washington",
            "option_d": "Benjamin Franklin",
            "correct_answer": "C",
            "subject": "History",
            "topic": "American History",
            "difficulty_level": "elementary",
            "explanation": "George Washington was the first President of the United States (1789-1797)"
        },
        {
            "question_text": "In which year did the Titanic sink?",
            "option_a": "1910",
            "option_b": "1911",
            "option_c": "1912",
            "option_d": "1913",
            "correct_answer": "C",
            "subject": "History",
            "topic": "Maritime History",
            "difficulty_level": "middle_school",
            "explanation": "The Titanic sank on April 15, 1912"
        },
        {
            "question_text": "Which ancient wonder of the world was located in Alexandria?",
            "option_a": "Hanging Gardens",
            "option_b": "Lighthouse of Alexandria",
            "option_c": "Colossus of Rhodes",
            "option_d": "Statue of Zeus",
            "correct_answer": "B",
            "subject": "History",
            "topic": "Ancient History",
            "difficulty_level": "high_school",
            "explanation": "The Lighthouse of Alexandria was one of the Seven Wonders of the Ancient World"
        },
        
        # PHILOSOPHY & LOGIC
        {
            "question_text": "Who is known as the father of Western philosophy?",
            "option_a": "Aristotle",
            "option_b": "Plato",
            "option_c": "Socrates",
            "option_d": "Pythagoras",
            "correct_answer": "C",
            "subject": "Philosophy",
            "topic": "Ancient Philosophy",
            "difficulty_level": "university",
            "explanation": "Socrates is often considered the father of Western philosophy"
        },
        {
            "question_text": "Complete the sequence: 2, 4, 8, 16, ?",
            "option_a": "24",
            "option_b": "32",
            "option_c": "30",
            "option_d": "28",
            "correct_answer": "B",
            "subject": "Mathematics",
            "topic": "Sequences",
            "difficulty_level": "middle_school",
            "explanation": "Each number is doubled: 2×2=4, 4×2=8, 8×2=16, 16×2=32"
        },
        
        # ECONOMICS & BUSINESS
        {
            "question_text": "What does GDP stand for?",
            "option_a": "Gross Domestic Product",
            "option_b": "General Domestic Product",
            "option_c": "Global Domestic Product",
            "option_d": "Gross Development Product",
            "correct_answer": "A",
            "subject": "Economics",
            "topic": "Economic Indicators",
            "difficulty_level": "high_school",
            "explanation": "GDP stands for Gross Domestic Product"
        },
        {
            "question_text": "What is inflation?",
            "option_a": "Decrease in prices",
            "option_b": "Increase in prices",
            "option_c": "Stable prices",
            "option_d": "Variable prices",
            "correct_answer": "B",
            "subject": "Economics",
            "topic": "Economic Concepts",
            "difficulty_level": "high_school",
            "explanation": "Inflation is the general increase in prices over time"
        }
    ]
    
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    with SessionLocal() as db:
        try:
            # CLEAR the table first!
            db.query(QuestionBank).delete()
            db.commit()

            questions_added = 0
            for q_data in questions:
                question = QuestionBank(**q_data)
                db.add(question)
                questions_added += 1

            db.commit()
            print(f"✅ Successfully added {questions_added} questions to the database!")
            return questions_added

        except Exception as e:
            db.rollback()
            print(f"❌ Error adding questions: {e}")
            raise e

if __name__ == "__main__":
    populate_question_bank()
