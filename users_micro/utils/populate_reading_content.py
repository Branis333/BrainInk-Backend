"""
Sample reading content for testing the reading assistant feature
This script populates the database with age-appropriate content for K-3 students
"""

import asyncio
from datetime import datetime
from sqlalchemy.orm import Session
from db.connection import SessionLocal
from models.reading_assistant_models import ReadingContent, ReadingLevel, DifficultyLevel

# Sample content for different reading levels
SAMPLE_CONTENT = {
    ReadingLevel.KINDERGARTEN: {
        DifficultyLevel.ELEMENTARY: [
            {
                "title": "The Red Cat",
                "content": "I see a cat. The cat is red. The cat sits on a mat. The red cat is big.",
                "content_type": "story",
                "vocabulary_words": {
                    "cat": "a furry pet with whiskers",
                    "red": "a bright color like fire",
                    "mat": "a small rug or carpet",
                    "big": "large in size"
                },
                "learning_objectives": [
                    "Practice reading simple CVC words",
                    "Recognize sight words (I, see, the, is, on, a)",
                    "Understand basic sentence structure"
                ],
                "phonics_focus": ["short vowels", "simple consonants", "CVC words"]
            },
            {
                "title": "My Dog",
                "content": "My dog is brown. He runs fast. We play in the sun. I love my dog.",
                "content_type": "story",
                "vocabulary_words": {
                    "dog": "a friendly pet that barks",
                    "brown": "a color like dirt or wood",
                    "fast": "moving quickly",
                    "love": "to care about very much"
                },
                "learning_objectives": [
                    "Read simple sentences fluently",
                    "Practice sight words",
                    "Connect reading to personal experience"
                ],
                "phonics_focus": ["short vowels", "consonant sounds"]
            },
            {
                "title": "Colors Everywhere",
                "content": "Red apples. Blue sky. Green grass. Yellow sun. I see colors everywhere!",
                "content_type": "sentence",
                "vocabulary_words": {
                    "apples": "round red fruit that grows on trees",
                    "sky": "the space above us where clouds float",
                    "grass": "green plants that cover the ground",
                    "everywhere": "in all places"
                },
                "learning_objectives": [
                    "Identify color words",
                    "Practice reading descriptive phrases",
                    "Build vocabulary about nature"
                ],
                "phonics_focus": ["color words", "descriptive language"]
            }
        ],
        DifficultyLevel.MIDDLE_SCHOOL: [
            {
                "title": "The Magic Garden",
                "content": "Emma planted seeds in her small garden. Every day she watered them. The sun helped them grow. Soon, beautiful flowers bloomed everywhere. Emma was very happy with her colorful garden.",
                "content_type": "story",
                "vocabulary_words": {
                    "planted": "put seeds in the ground to grow",
                    "garden": "a place where plants and flowers grow",
                    "watered": "gave water to help plants grow",
                    "bloomed": "when flowers open up and show their pretty colors",
                    "colorful": "having many different colors"
                },
                "learning_objectives": [
                    "Read longer sentences with confidence",
                    "Understand sequence of events",
                    "Learn about nature and gardening"
                ],
                "phonics_focus": ["consonant blends", "long vowel sounds", "compound words"]
            }
        ]
    },
    
    ReadingLevel.GRADE_1: {
        DifficultyLevel.ELEMENTARY: [
            {
                "title": "The Helpful Friend",
                "content": "Sam saw his friend drop her books. He quickly picked them up for her. 'Thank you!' she said with a big smile. Sam felt good about helping his friend. Being kind makes everyone happy.",
                "content_type": "story",
                "vocabulary_words": {
                    "helpful": "willing to help others",
                    "quickly": "doing something fast",
                    "smile": "happy look on someone's face",
                    "kind": "nice and caring to others"
                },
                "learning_objectives": [
                    "Read dialogue and understand quotation marks",
                    "Learn about friendship and kindness",
                    "Practice reading with expression"
                ],
                "phonics_focus": ["digraphs (th, ch, sh)", "sight words", "compound words"]
            },
            {
                "title": "Animals in Winter",
                "content": "When winter comes, animals get ready. Bears sleep in caves. Birds fly to warm places. Squirrels save nuts to eat. Each animal has a special way to stay safe and warm.",
                "content_type": "paragraph",
                "vocabulary_words": {
                    "winter": "the cold season with snow",
                    "caves": "holes in rocks or mountains",
                    "warm": "not cold, cozy",
                    "special": "different from others, unique"
                },
                "learning_objectives": [
                    "Learn about animal behaviors",
                    "Practice reading informational text",
                    "Build science vocabulary"
                ],
                "phonics_focus": ["vowel teams", "r-controlled vowels"]
            }
        ]
    },
    
    ReadingLevel.GRADE_2: {
        DifficultyLevel.ELEMENTARY: [
            {
                "title": "The School Library Adventure",
                "content": "Maria loved visiting the school library every Tuesday. Mrs. Chen, the librarian, always helped her find exciting books about dinosaurs and space adventures. Today, Maria discovered a new series about a brave girl who travels around the world. She couldn't wait to read the first chapter during reading time.",
                "content_type": "story",
                "vocabulary_words": {
                    "library": "a place with lots of books to read and borrow",
                    "librarian": "a person who works in a library and helps people find books",
                    "discovered": "found something new and interesting",
                    "series": "books that tell connected stories",
                    "chapter": "a section of a book"
                },
                "learning_objectives": [
                    "Read longer paragraphs with comprehension",
                    "Learn about library skills and resources",
                    "Practice reading multisyllabic words"
                ],
                "phonics_focus": ["multisyllabic words", "vowel patterns", "prefixes and suffixes"]
            }
        ]
    },
    
    ReadingLevel.GRADE_3: {
        DifficultyLevel.ELEMENTARY: [
            {
                "title": "The Science Fair Project",
                "content": "Alex had been working on his science fair project for three weeks. He wanted to show how plants grow differently in various types of light. He carefully measured each plant every day and recorded the results in his notebook. Some plants grew tall and strong in bright sunlight, while others struggled in the dark corner of his room. On the day of the science fair, Alex proudly presented his findings to the judges. He explained how sunlight helps plants make their own food through photosynthesis. The judges were impressed by his careful observations and clear explanations.",
                "content_type": "story",
                "vocabulary_words": {
                    "project": "a special task or assignment to complete",
                    "various": "many different kinds",
                    "measured": "found out the size or amount of something",
                    "recorded": "wrote down information to remember it",
                    "struggled": "had difficulty or problems",
                    "observations": "things you notice by watching carefully",
                    "photosynthesis": "the way plants use sunlight to make food"
                },
                "learning_objectives": [
                    "Read and comprehend longer narrative text",
                    "Learn scientific vocabulary and concepts",
                    "Practice reading with fluency and expression",
                    "Understand sequence and cause-and-effect relationships"
                ],
                "phonics_focus": ["advanced phonics patterns", "scientific vocabulary", "complex sentence structures"]
            }
        ]
    }
}

async def populate_reading_content():
    """Populate database with sample reading content"""
    
    db = SessionLocal()
    
    try:
        # Check if content already exists
        existing_content = db.query(ReadingContent).first()
        if existing_content:
            print("Reading content already exists in database. Skipping population.")
            return
        
        content_count = 0
        
        for reading_level, difficulty_dict in SAMPLE_CONTENT.items():
            for difficulty_level, content_list in difficulty_dict.items():
                for content_data in content_list:
                    
                    # Calculate metrics
                    word_count = len(content_data["content"].split())
                    estimated_time = word_count * 2  # 2 seconds per word for beginners
                    
                    # Create content record
                    new_content = ReadingContent(
                        title=content_data["title"],
                        content=content_data["content"],
                        content_type=content_data["content_type"],
                        reading_level=reading_level,
                        difficulty_level=difficulty_level,
                        vocabulary_words=content_data["vocabulary_words"],
                        learning_objectives=content_data["learning_objectives"],
                        phonics_focus=content_data["phonics_focus"],
                        word_count=word_count,
                        estimated_reading_time=estimated_time,
                        complexity_score=_calculate_complexity_score(reading_level, difficulty_level, word_count),
                        created_by=1,  # System user ID
                        is_active=True
                    )
                    
                    db.add(new_content)
                    content_count += 1
        
        db.commit()
        print(f"✅ Successfully populated {content_count} reading content items")
        
        # Print summary
        for reading_level in ReadingLevel:
            count = db.query(ReadingContent).filter_by(reading_level=reading_level).count()
            print(f"   - {reading_level.value}: {count} items")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error populating reading content: {e}")
        
    finally:
        db.close()

def _calculate_complexity_score(reading_level: ReadingLevel, difficulty_level: DifficultyLevel, word_count: int) -> float:
    """Calculate a complexity score based on reading level and other factors"""
    
    base_scores = {
        ReadingLevel.KINDERGARTEN: 20,
        ReadingLevel.GRADE_1: 40,
        ReadingLevel.GRADE_2: 60,
        ReadingLevel.GRADE_3: 80
    }
    
    difficulty_modifiers = {
        DifficultyLevel.ELEMENTARY: 0,
        DifficultyLevel.MIDDLE_SCHOOL: 10,
        DifficultyLevel.HIGH_SCHOOL: 20
    }
    
    base_score = base_scores[reading_level]
    difficulty_modifier = difficulty_modifiers[difficulty_level]
    word_count_factor = min(word_count / 10, 10)  # Cap at 10 points for word count
    
    return min(base_score + difficulty_modifier + word_count_factor, 100)

if __name__ == "__main__":
    asyncio.run(populate_reading_content())
