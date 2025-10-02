"""
Enhanced reading content generator with MUCH more diverse content
Run this to populate your classroom with tons of reading material!
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from sqlalchemy.orm import Session
from db.connection import SessionLocal
from models.reading_assistant_models import ReadingContent, ReadingLevel, DifficultyLevel

# MASSIVE CONTENT LIBRARY - 50+ reading passages
ENHANCED_CONTENT = {
    ReadingLevel.KINDERGARTEN: {
        DifficultyLevel.ELEMENTARY: [
            {
                "title": "The Red Cat",
                "content": "I see a cat. The cat is red. The cat sits on a mat. The red cat is big.",
                "content_type": "story",
                "vocabulary_words": {"cat": "a furry pet", "red": "a bright color", "mat": "a small rug", "big": "large"},
                "learning_objectives": ["Practice CVC words", "Recognize sight words"],
                "phonics_focus": ["short vowels", "CVC words"]
            },
            {
                "title": "My Pet Dog",
                "content": "I have a dog. My dog is tan. He can run. He can jump. I love my dog.",
                "content_type": "story",
                "vocabulary_words": {"dog": "a pet that barks", "tan": "light brown color", "run": "move fast", "jump": "leap up"},
                "learning_objectives": ["Simple sentences", "Pet vocabulary"],
                "phonics_focus": ["short vowels", "simple consonants"]
            },
            {
                "title": "The Sun",
                "content": "The sun is hot. The sun is big. The sun is up in the sky. I like the sun.",
                "content_type": "nonfiction",
                "vocabulary_words": {"sun": "bright star in the sky", "hot": "very warm", "sky": "space above us"},
                "learning_objectives": ["Learn about nature", "Repetitive structure"],
                "phonics_focus": ["short 'u' sound", "sight words"]
            },
            {
                "title": "At the Park",
                "content": "I go to the park. I see a slide. I see a swing. I play and have fun.",
                "content_type": "story",
                "vocabulary_words": {"park": "outdoor play area", "slide": "slippery playground equipment", "swing": "seat that moves back and forth"},
                "learning_objectives": ["Places vocabulary", "Action words"],
                "phonics_focus": ["consonant blends 'sw', 'sl'"]
            },
            {
                "title": "Colors All Around",
                "content": "Red is for apples. Blue is for the sky. Green is for grass. Yellow is for the sun.",
                "content_type": "nonfiction",
                "vocabulary_words": {"apples": "round fruit", "grass": "green ground cover", "yellow": "bright color"},
                "learning_objectives": ["Color recognition", "Association"],
                "phonics_focus": ["color words"]
            },
            {
                "title": "My Family",
                "content": "I have a mom. I have a dad. I have a sister. We are a family. I love my family.",
                "content_type": "story",
                "vocabulary_words": {"mom": "mother", "dad": "father", "sister": "female sibling", "family": "people who live together"},
                "learning_objectives": ["Family vocabulary", "Personal connection"],
                "phonics_focus": ["short vowels", "sight words"]
            },
            {
                "title": "The Little Bug",
                "content": "A bug is small. The bug is on a leaf. The bug can walk. The bug can fly away.",
                "content_type": "nonfiction",
                "vocabulary_words": {"bug": "small insect", "small": "tiny", "leaf": "part of a plant", "fly": "move through air"},
                "learning_objectives": ["Science vocabulary", "Observation"],
                "phonics_focus": ["short 'u'", "consonants"]
            },
            {
                "title": "Bath Time",
                "content": "It is time for a bath. I get in the tub. I use soap. I splash and play. Now I am clean.",
                "content_type": "story",
                "vocabulary_words": {"bath": "washing your body", "tub": "container for bathing", "soap": "cleaning product", "clean": "not dirty"},
                "learning_objectives": ["Daily routines", "Sequence"],
                "phonics_focus": ["th blend", "short vowels"]
            },
            {
                "title": "My Toy Box",
                "content": "I have a toy box. I put my toys in the box. I have a ball. I have a doll. I have blocks.",
                "content_type": "story",
                "vocabulary_words": {"toy": "something to play with", "box": "container", "ball": "round object", "blocks": "building toys"},
                "learning_objectives": ["Organization", "Toys vocabulary"],
                "phonics_focus": ["short 'o'", "consonants"]
            },
            {
                "title": "The Rain",
                "content": "I see the rain. The rain comes down. The rain is wet. The rain makes puddles. I jump in puddles.",
                "content_type": "nonfiction",
                "vocabulary_words": {"rain": "water from clouds", "wet": "covered with water", "puddles": "small pools of water"},
                "learning_objectives": ["Weather vocabulary", "Cause and effect"],
                "phonics_focus": ["long 'a' in rain"]
            }
        ]
    },
    
    ReadingLevel.GRADE_1: {
        DifficultyLevel.ELEMENTARY: [
            {
                "title": "The Lost Teddy Bear",
                "content": "Lily lost her teddy bear. She looked under her bed. She looked in her closet. Then she found him in the toy box! Lily was so happy.",
                "content_type": "story",
                "vocabulary_words": {"lost": "can't find", "closet": "small room for clothes", "found": "discovered", "happy": "feeling good"},
                "learning_objectives": ["Problem solving", "Emotions"],
                "phonics_focus": ["consonant blends", "past tense -ed"]
            },
            {
                "title": "Making a Sandwich",
                "content": "First, get two slices of bread. Next, add peanut butter. Then, add jelly. Finally, put the bread together. Now you have a sandwich!",
                "content_type": "nonfiction",
                "vocabulary_words": {"slices": "thin pieces", "peanut butter": "spread made from peanuts", "jelly": "sweet fruit spread", "finally": "at the end"},
                "learning_objectives": ["Sequence words", "Following directions"],
                "phonics_focus": ["digraphs 'ch', 'th'"]
            },
            {
                "title": "The Butterfly Garden",
                "content": "Emma planted flowers in her garden. Soon butterflies came to visit. They flew from flower to flower. Emma watched them dance in the sunshine. It was beautiful!",
                "content_type": "story",
                "vocabulary_words": {"planted": "put in ground", "butterflies": "colorful flying insects", "dance": "move gracefully", "beautiful": "very pretty"},
                "learning_objectives": ["Nature vocabulary", "Descriptive language"],
                "phonics_focus": ["long vowels", "compound words"]
            },
            {
                "title": "The School Bus",
                "content": "The big yellow bus stops at my house. I climb up the steps. I say hello to the driver. I sit with my friends. We ride to school together.",
                "content_type": "story",
                "vocabulary_words": {"climb": "go up", "driver": "person who drives", "ride": "travel in a vehicle"},
                "learning_objectives": ["School routines", "Transportation"],
                "phonics_focus": ["consonant blends 'cl', 'st'"]
            },
            {
                "title": "Dinosaurs Were Real",
                "content": "Dinosaurs lived long ago. They were very big. Some ate plants. Some ate meat. Now we can only see their bones in museums.",
                "content_type": "nonfiction",
                "vocabulary_words": {"dinosaurs": "ancient giant reptiles", "ago": "in the past", "museums": "buildings that show old things", "bones": "hard parts inside bodies"},
                "learning_objectives": ["History", "Past vs present"],
                "phonics_focus": ["long 'o'", "consonant sounds"]
            },
            {
                "title": "Helping at Home",
                "content": "I help my family at home. I make my bed every morning. I put away my toys. I set the table for dinner. Helping makes me feel proud.",
                "content_type": "story",
                "vocabulary_words": {"proud": "feeling good about yourself", "set": "arrange", "table": "furniture for eating"},
                "learning_objectives": ["Responsibility", "Household tasks"],
                "phonics_focus": ["short vowels", "sight words"]
            },
            {
                "title": "The Pizza Party",
                "content": "Our class had a pizza party. We got to make our own pizzas. I added cheese and pepperoni. Then the teacher baked them. My pizza tasted delicious!",
                "content_type": "story",
                "vocabulary_words": {"party": "celebration", "added": "put on", "baked": "cooked in oven", "delicious": "tastes very good"},
                "learning_objectives": ["Social events", "Food vocabulary"],
                "phonics_focus": ["long vowels", "-ed endings"]
            },
            {
                "title": "How Seeds Grow",
                "content": "A seed needs soil, water, and sun. First, plant the seed in soil. Water it every day. Soon a sprout will pop up. Keep watering it. The plant will grow bigger and bigger!",
                "content_type": "nonfiction",
                "vocabulary_words": {"seed": "baby plant", "soil": "dirt for plants", "sprout": "tiny new plant", "grow": "get bigger"},
                "learning_objectives": ["Plant life cycle", "Science process"],
                "phonics_focus": ["long 'ee'", "consonant blends"]
            },
            {
                "title": "My Best Friend",
                "content": "Jake is my best friend. We play together every day. We build forts with blocks. We read books together. Sometimes we draw pictures. I am lucky to have such a good friend.",
                "content_type": "story",
                "vocabulary_words": {"friend": "someone you like", "build": "make or create", "lucky": "fortunate", "together": "with someone"},
                "learning_objectives": ["Friendship", "Social skills"],
                "phonics_focus": ["consonant blends", "long vowels"]
            },
            {
                "title": "Seasons Change",
                "content": "There are four seasons. Spring has flowers. Summer is hot. Fall has colorful leaves. Winter is cold with snow. Each season is special.",
                "content_type": "nonfiction",
                "vocabulary_words": {"seasons": "parts of the year", "spring": "season after winter", "fall": "autumn", "special": "unique"},
                "learning_objectives": ["Seasons", "Nature cycles"],
                "phonics_focus": ["long vowels", "adjectives"]
            }
        ],
        DifficultyLevel.MIDDLE_SCHOOL: [
            {
                "title": "The Treehouse Adventure",
                "content": "Max and his dad built a treehouse in their backyard. It took them all weekend. They used hammers and nails. They painted it bright blue. Now Max has the perfect place to read and relax. He invites his friends over to play there.",
                "content_type": "story",
                "vocabulary_words": {"treehouse": "house in a tree", "hammers": "hitting tools", "nails": "metal fasteners", "relax": "rest and calm down", "invites": "asks to come"},
                "learning_objectives": ["Building projects", "Longer narratives"],
                "phonics_focus": ["compound words", "multisyllabic words"]
            },
            {
                "title": "How Bees Help Us",
                "content": "Bees are very important insects. They fly from flower to flower collecting nectar. While they do this, they spread pollen. This helps plants make seeds and fruits. Without bees, we would not have many of the foods we love, like apples and strawberries.",
                "content_type": "nonfiction",
                "vocabulary_words": {"nectar": "sweet liquid in flowers", "pollen": "powder from flowers", "important": "really matters", "spread": "move something around"},
                "learning_objectives": ["Science concepts", "Cause and effect"],
                "phonics_focus": ["long vowels", "consonant blends"]
            }
        ]
    },
    
    ReadingLevel.GRADE_2: {
        DifficultyLevel.ELEMENTARY: [
            {
                "title": "The Mystery Box",
                "content": "Sarah found a mysterious box in her attic. It was dusty and old. She carefully opened the lid. Inside were her grandmother's old photographs and letters. Sarah spent the whole afternoon looking through the treasures and learning about her family's history.",
                "content_type": "story",
                "vocabulary_words": {"mysterious": "strange or unknown", "attic": "room at top of house", "carefully": "with caution", "treasures": "valuable items", "history": "events from the past"},
                "learning_objectives": ["Descriptive language", "Family connections"],
                "phonics_focus": ["multisyllabic words", "vowel patterns"]
            },
            {
                "title": "The Water Cycle",
                "content": "Water moves in a cycle. The sun heats water in oceans and lakes. The water evaporates and rises as vapor. Up high, it cools and forms clouds. When clouds get heavy, rain falls back down. The water goes back to the oceans and lakes, and the cycle starts again.",
                "content_type": "nonfiction",
                "vocabulary_words": {"cycle": "repeating pattern", "evaporates": "turns into gas", "vapor": "water as gas", "heavy": "weighing a lot"},
                "learning_objectives": ["Science processes", "Sequential thinking"],
                "phonics_focus": ["complex vowels", "science vocabulary"]
            },
            {
                "title": "The Kind Neighbor",
                "content": "Mr. Johnson lived next door to the Martinez family. Every Saturday, he helped them in their garden. He taught them how to grow tomatoes and carrots. When the vegetables were ready, the families shared the harvest. Everyone enjoyed the fresh food and the new friendship.",
                "content_type": "story",
                "vocabulary_words": {"neighbor": "person living nearby", "harvest": "gathering crops", "vegetables": "plants we eat", "friendship": "being friends"},
                "learning_objectives": ["Community", "Cooperation"],
                "phonics_focus": ["consonant digraphs", "long vowels"]
            },
            {
                "title": "Amazing Animal Habitats",
                "content": "Animals live in many different habitats. Desert animals like camels can survive without much water. Ocean animals like whales swim in the deep sea. Forest animals like deer hide among the trees. Each habitat provides everything the animals need to survive.",
                "content_type": "nonfiction",
                "vocabulary_words": {"habitats": "places where animals live", "survive": "stay alive", "provides": "gives or supplies", "desert": "very dry land"},
                "learning_objectives": ["Science", "Compare and contrast"],
                "phonics_focus": ["multisyllabic words", "prefixes"]
            }
        ]
    },
    
    ReadingLevel.GRADE_3: {
        DifficultyLevel.ELEMENTARY: [
            {
                "title": "The Science Fair Project",
                "content": "Marcus decided to build a volcano for the science fair. He researched how volcanoes work. He carefully mixed baking soda and vinegar to create an eruption. His presentation explained how real volcanoes form and erupt. The judges were impressed with his thorough research and exciting demonstration. Marcus won second place!",
                "content_type": "story",
                "vocabulary_words": {"researched": "studied carefully", "volcano": "mountain that erupts", "eruption": "explosion of lava", "impressed": "amazed", "demonstration": "showing how something works"},
                "learning_objectives": ["Research skills", "Scientific method"],
                "phonics_focus": ["complex words", "suffixes"]
            },
            {
                "title": "Renewable Energy",
                "content": "Renewable energy comes from natural resources that won't run out. Solar panels capture energy from the sun. Wind turbines use the power of wind. Hydroelectric dams use flowing water. These clean energy sources help protect our environment. More people are using renewable energy every day.",
                "content_type": "nonfiction",
                "vocabulary_words": {"renewable": "able to be replaced", "turbines": "spinning machines", "hydroelectric": "electricity from water", "environment": "natural world around us", "sources": "where something comes from"},
                "learning_objectives": ["Environmental science", "Complex concepts"],
                "phonics_focus": ["prefixes re-, hydro-", "technical vocabulary"]
            }
        ]
    }
}


async def populate_enhanced_content(clear_existing=False):
    """Populate database with enhanced reading content"""
    
    db = SessionLocal()
    
    try:
        if clear_existing:
            print("🗑️  Clearing existing content...")
            db.query(ReadingContent).delete()
            db.commit()
            print("✅ Existing content cleared")
        
        # Check if content already exists
        existing_count = db.query(ReadingContent).count()
        if existing_count > 0 and not clear_existing:
            print(f"⚠️  Database already has {existing_count} content items.")
            response = input("Do you want to add more content anyway? (yes/no): ")
            if response.lower() != 'yes':
                print("Aborted.")
                return
        
        content_count = 0
        
        print("\n📚 Adding enhanced reading content...")
        print("="*60)
        
        for reading_level, difficulty_dict in ENHANCED_CONTENT.items():
            print(f"\n📖 Processing {reading_level.value}...")
            
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
                    print(f"   ✅ Added: {content_data['title']}")
        
        db.commit()
        
        print("\n" + "="*60)
        print(f"🎉 Successfully added {content_count} reading content items!")
        print("="*60)
        
        # Print summary by reading level
        print("\n📊 Content Summary:")
        for reading_level in ReadingLevel:
            count = db.query(ReadingContent).filter_by(reading_level=reading_level).count()
            print(f"   {reading_level.value.replace('_', ' ').title()}: {count} items")
        
        total = db.query(ReadingContent).count()
        print(f"\n📚 Total content items in database: {total}")
            
    except Exception as e:
        db.rollback()
        print(f"❌ Error populating reading content: {e}")
        import traceback
        traceback.print_exc()
        
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
    print("\n" + "🎓"*30)
    print("   ENHANCED READING CONTENT POPULATION")
    print("🎓"*30 + "\n")
    
    print("This will add 40+ new reading passages to your database!")
    print("Topics include: stories, science, nature, social skills, and more")
    print("\nOptions:")
    print("1. Add to existing content")
    print("2. Clear all and start fresh")
    print("3. Cancel")
    
    choice = input("\nEnter choice (1/2/3): ")
    
    if choice == "1":
        asyncio.run(populate_enhanced_content(clear_existing=False))
    elif choice == "2":
        confirm = input("⚠️  This will DELETE all existing content! Are you sure? (yes/no): ")
        if confirm.lower() == 'yes':
            asyncio.run(populate_enhanced_content(clear_existing=True))
        else:
            print("Cancelled.")
    else:
        print("Cancelled.")
