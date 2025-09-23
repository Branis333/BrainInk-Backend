import os
import json
import asyncio
import tempfile
import mimetypes
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import re
import google.generativeai as genai
from pydantic import BaseModel

# Configuration for Gemini API
class GeminiConfig:
    def __init__(self):
        # Try GEMINI_API_KEY first, then fall back to GOOGLE_API_KEY
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY or GOOGLE_API_KEY environment variable not set")
        
        # Use gemini-1.5-flash for free tier, allow override with GEMINI_MODEL
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        
        print(f"🔑 Configuring Gemini AI with API key: {self.api_key[:10]}...{self.api_key[-4:]}")
        print(f"🤖 Using model: {self.model_name} (free tier optimized)")
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(self.model_name)

# Data structures for course generation
class CourseBlock(BaseModel):
    week: int
    block_number: int
    title: str
    description: str
    learning_objectives: List[str]
    content: str
    duration_minutes: int
    resources: List[Dict[str, str]]  # [{"type": "video", "title": "...", "url": "..."}]
    assignments: List[Dict[str, Any]]

class GeneratedCourse(BaseModel):
    title: str
    subject: str
    description: str
    age_min: int
    age_max: int
    difficulty_level: str
    total_weeks: int
    blocks_per_week: int
    textbook_source: str
    blocks: List[CourseBlock]
    overall_assignments: List[Dict[str, Any]]

class GeminiService:
    def __init__(self):
        self.config = GeminiConfig()
        
    async def analyze_textbook_and_generate_course(
        self, 
        textbook_content: str, 
        course_title: str,
        subject: str,
        target_age_range: tuple,
        total_weeks: int,
        blocks_per_week: int,
        difficulty_level: str = "intermediate"
    ) -> GeneratedCourse:
        """
        Analyze textbook content and generate course progressively, block by block
        This prevents quota issues by processing one block at a time with delays
        """
        
        try:
            # Progressive block-by-block course generation
            print(f"🎯 Starting progressive course generation: {total_weeks} weeks × {blocks_per_week} blocks")
            
            # Step 1: Analyze textbook structure and create course outline
            course_outline = await self._analyze_textbook_structure(
                textbook_content, course_title, subject, target_age_range, 
                total_weeks, blocks_per_week, difficulty_level
            )
            
            print(f"📋 Course outline created: {course_outline['title']}")
            print(f"📚 Content sections identified: {len(course_outline.get('content_sections', []))}")
            
            # Step 2: Generate blocks progressively
            total_blocks = total_weeks * blocks_per_week
            generated_blocks = []
            
            print(f"🔄 Generating {total_blocks} blocks progressively...")
            
            for block_num in range(1, total_blocks + 1):
                week_num = ((block_num - 1) // blocks_per_week) + 1
                block_in_week = ((block_num - 1) % blocks_per_week) + 1
                
                print(f"⏳ Generating Block {block_num}/{total_blocks} (Week {week_num}, Block {block_in_week})")
                
                # Generate individual block
                block_data = await self._generate_single_block(
                    textbook_content, course_outline, week_num, block_in_week, 
                    block_num, total_blocks, subject, target_age_range, difficulty_level
                )
                
                generated_blocks.append(block_data)
                
                # Add delay between blocks to avoid rate limiting (2 seconds)
                if block_num < total_blocks:
                    await asyncio.sleep(2)
                    print(f"⏳ Waiting 2 seconds before next block...")
                    print(f"⏱️  Waiting 2 seconds before next block...")
                    await asyncio.sleep(2)
            
            print(f"✅ All {len(generated_blocks)} blocks generated successfully!")
            
            # Step 3: Generate overall course assignments
            print(f"📝 Generating overall course assignments...")
            overall_assignments = await self._generate_overall_assignments(
                course_outline, generated_blocks, total_weeks
            )
            
            # Step 4: Assemble final course data
            course_data = {
                "title": course_outline["title"],
                "subject": course_outline["subject"],
                "description": course_outline["description"],
                "age_min": course_outline["age_min"],
                "age_max": course_outline["age_max"],
                "difficulty_level": course_outline["difficulty_level"],
                "total_weeks": total_weeks,
                "blocks_per_week": blocks_per_week,
                "textbook_source": course_outline.get("textbook_source", "Uploaded textbook"),
                "blocks": generated_blocks,
                "overall_assignments": overall_assignments
            }
            
            print(f"🎉 Course generation complete: '{course_data['title']}'")
            return GeneratedCourse(**course_data)
            
        except Exception as e:
            raise Exception(f"Failed to generate course: {str(e)}")

    async def _analyze_textbook_structure(
        self, textbook_content: str, course_title: str, subject: str, 
        target_age_range: tuple, total_weeks: int, blocks_per_week: int, difficulty_level: str
    ) -> Dict[str, Any]:
        """
        Analyze textbook structure and create a course outline
        This is a lightweight analysis that doesn't consume many tokens
        """
        age_min, age_max = target_age_range
        
        # Check if textbook_content is a Gemini file URI
        if textbook_content.startswith("GEMINI_FILE_URI:"):
            gemini_file_uri = textbook_content.replace("GEMINI_FILE_URI:", "")
            uploaded_file = genai.get_file(gemini_file_uri)
            
            structure_prompt = f"""
            Analyze the uploaded textbook file and create a high-level course structure outline.
            
            COURSE REQUIREMENTS:
            - Title: {course_title}
            - Subject: {subject}
            - Target Age: {age_min}-{age_max} years
            - Duration: {total_weeks} weeks ({blocks_per_week} blocks per week = {total_weeks * blocks_per_week} total blocks)
            - Difficulty: {difficulty_level}
            
            Create a JSON outline with this structure:
            {{
                "title": "{course_title}",
                "subject": "{subject}",
                "description": "Brief course description (1-2 sentences)",
                "age_min": {age_min},
                "age_max": {age_max},
                "difficulty_level": "{difficulty_level}",
                "textbook_source": "Brief description of the textbook",
                "content_sections": [
                    {{
                        "section_title": "Section 1 Title",
                        "topics": ["Topic 1", "Topic 2", "Topic 3"],
                        "estimated_blocks": 2,
                        "difficulty": "beginner|intermediate|advanced"
                    }},
                    {{
                        "section_title": "Section 2 Title", 
                        "topics": ["Topic 4", "Topic 5"],
                        "estimated_blocks": 3,
                        "difficulty": "intermediate"
                    }}
                ],
                "learning_progression": "How topics build upon each other",
                "key_concepts": ["Main concept 1", "Main concept 2", "Main concept 3"]
            }}
            
            INSTRUCTIONS:
            - Identify main sections/chapters in the textbook
            - Map content to the {total_weeks * blocks_per_week} blocks needed
            - Ensure logical progression through material
            - Keep response concise and focused on structure
            """
            
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                [uploaded_file, structure_prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=512,  # Reduced for free tier
                    response_mime_type="application/json"
                )
            )
        else:
            # Handle direct text content
            structure_prompt = f"""
            Analyze the following textbook content and create a high-level course structure outline.
            
            TEXTBOOK CONTENT:
            {textbook_content[:2000]}... # First 2000 chars for structure analysis
            
            COURSE REQUIREMENTS:
            - Title: {course_title}
            - Subject: {subject}
            - Target Age: {age_min}-{age_max} years
            - Duration: {total_weeks} weeks ({blocks_per_week} blocks per week = {total_weeks * blocks_per_week} total blocks)
            - Difficulty: {difficulty_level}
            
            Create a JSON outline with the same structure as above...
            """
            
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                structure_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=512,
                    response_mime_type="application/json"
                )
            )
        
        return json.loads(response.text)

    async def _generate_single_block(
        self, textbook_content: str, course_outline: Dict, week_num: int, 
        block_in_week: int, block_num: int, total_blocks: int, subject: str, 
        target_age_range: tuple, difficulty_level: str
    ) -> Dict[str, Any]:
        """
        Generate a single course block based on textbook content and course outline
        """
        age_min, age_max = target_age_range
        
        # Determine which content section this block should cover
        content_sections = course_outline.get("content_sections", [])
        blocks_per_section = max(1, total_blocks // len(content_sections)) if content_sections else 1
        section_index = min((block_num - 1) // blocks_per_section, len(content_sections) - 1)
        current_section = content_sections[section_index] if content_sections else {"section_title": f"Week {week_num} Content", "topics": []}
        
        if textbook_content.startswith("GEMINI_FILE_URI:"):
            gemini_file_uri = textbook_content.replace("GEMINI_FILE_URI:", "")
            uploaded_file = genai.get_file(gemini_file_uri)
            
            block_prompt = f"""
            Generate a detailed learning block based on the uploaded textbook content.
            
            BLOCK CONTEXT:
            - Block {block_num} of {total_blocks} (Week {week_num}, Block {block_in_week})
            - Target Section: {current_section.get('section_title', 'General Content')}
            - Section Topics: {', '.join(current_section.get('topics', []))}
            - Subject: {subject}
            - Target Age: {age_min}-{age_max}
            - Difficulty: {difficulty_level}
            
            COURSE CONTEXT:
            Course Title: {course_outline.get('title', 'Course')}
            Course Description: {course_outline.get('description', '')}
            Previous Learning: {"First block" if block_num == 1 else f"Building on previous {block_num-1} blocks"}
            
            Generate a JSON block with this exact structure:
            {{
                "week": {week_num},
                "block_number": {block_in_week},
                "title": "Specific block title from textbook content",
                "description": "What students will learn in this block",
                "learning_objectives": [
                    "Specific objective 1 from textbook",
                    "Specific objective 2 from textbook",
                    "Specific objective 3 from textbook"
                ],
                "content": "Detailed lesson content extracted from textbook (400-600 words)",
                "duration_minutes": 45,
                "visual_elements": ["Any diagrams/images referenced", "Charts or illustrations"],
                "resources": [
                    {{"type": "article", "title": "Resource Title", "url": "placeholder", "search_query": "specific search terms"}},
                    {{"type": "video", "title": "Video Title", "url": "placeholder", "search_query": "YouTube search terms"}}
                ],
                "assignments": [
                    {{
                        "title": "Block Assignment Title",
                        "description": "Assignment based on block content",
                        "type": "homework",
                        "duration_minutes": 30,
                        "points": 100,
                        "rubric": "Clear grading criteria",
                        "due_days_after_block": 3
                    }}
                ]
            }}
            
            IMPORTANT:
            - Focus ONLY on content for THIS specific block
            - Extract relevant content from the textbook for this section
            - Ensure age-appropriate language and complexity
            - Build on previous blocks if this is not the first block
            - Make it comprehensive but focused
            """
            
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                [uploaded_file, block_prompt],
                generation_config=genai.types.GenerationConfig(
                    temperature=0.6,
                    max_output_tokens=1024,  # Reduced for free tier
                    response_mime_type="application/json"
                )
            )
        else:
            # Handle direct text content - extract relevant portion
            content_chunk_size = len(textbook_content) // total_blocks
            start_pos = (block_num - 1) * content_chunk_size
            end_pos = min(start_pos + content_chunk_size + 500, len(textbook_content))  # Overlap for context
            content_chunk = textbook_content[start_pos:end_pos]
            
            block_prompt = f"""
            Generate a detailed learning block based on this textbook content section.
            
            TEXTBOOK CONTENT (Section {block_num}):
            {content_chunk}
            
            BLOCK CONTEXT:
            - Block {block_num} of {total_blocks} (Week {week_num}, Block {block_in_week})
            - Subject: {subject}
            - Target Age: {age_min}-{age_max}
            - Difficulty: {difficulty_level}
            
            Generate the same JSON structure as above...
            """
            
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                block_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.6,
                    max_output_tokens=1024,
                    response_mime_type="application/json"
                )
            )
        
        block_data = json.loads(response.text)
        
        # Ensure correct week and block numbers
        block_data["week"] = week_num
        block_data["block_number"] = block_in_week
        
        return block_data

    async def _generate_overall_assignments(
        self, course_outline: Dict, generated_blocks: List[Dict], total_weeks: int
    ) -> List[Dict[str, Any]]:
        """
        Generate overall course assignments (midterms, finals, projects)
        """
        print(f"📋 Creating overall course assignments...")
        
        assignments_prompt = f"""
        Create overall course assignments based on the course content.
        
        COURSE CONTEXT:
        Title: {course_outline.get('title', 'Course')}
        Subject: {course_outline.get('subject', 'Subject')}
        Total Weeks: {total_weeks}
        Total Blocks: {len(generated_blocks)}
        Key Concepts: {', '.join(course_outline.get('key_concepts', []))}
        
        GENERATED BLOCKS SUMMARY:
        {chr(10).join([f"Week {block['week']}, Block {block['block_number']}: {block.get('title', 'Block')}" for block in generated_blocks[:5]])}
        {"... (and more blocks)" if len(generated_blocks) > 5 else ""}
        
        Create 2-3 major assignments in JSON format:
        [
            {{
                "title": "Midterm Assessment",
                "description": "Comprehensive assessment covering the first half of the course",
                "type": "assessment",
                "week_assigned": {total_weeks // 2},
                "duration_minutes": 60,
                "points": 200,
                "rubric": "Detailed rubric covering key concepts",
                "due_days_after_assignment": 7
            }},
            {{
                "title": "Final Project",
                "description": "Capstone project demonstrating mastery of course objectives",
                "type": "project", 
                "week_assigned": {max(1, total_weeks - 2)},
                "duration_minutes": 120,
                "points": 300,
                "rubric": "Project evaluation criteria",
                "due_days_after_assignment": 14
            }}
        ]
        """
        
        try:
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                assignments_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=512,
                    response_mime_type="application/json"
                )
            )
            
            return json.loads(response.text)
        except Exception as e:
            print(f"⚠️ Failed to generate overall assignments, using defaults: {str(e)}")
            # Fallback assignments
            return [
                {
                    "title": "Midterm Assessment",
                    "description": f"Comprehensive assessment covering the first half of {course_outline.get('title', 'the course')}",
                    "type": "assessment",
                    "week_assigned": total_weeks // 2,
                    "duration_minutes": 60,
                    "points": 200,
                    "rubric": "Knowledge demonstration, application, and analysis",
                    "due_days_after_assignment": 7
                },
                {
                    "title": "Final Project",
                    "description": f"Capstone project demonstrating mastery of {course_outline.get('subject', 'course')} objectives",
                    "type": "project",
                    "week_assigned": max(1, total_weeks - 2),
                    "duration_minutes": 120,
                    "points": 300,
                    "rubric": "Project completeness, creativity, and understanding demonstration",
                    "due_days_after_assignment": 14
                }
            ]

    def _create_course_generation_prompt(
        self, textbook_content: str, course_title: str, subject: str, 
        target_age_range: tuple, total_weeks: int, blocks_per_week: int, difficulty_level: str
    ) -> str:
        """Create a comprehensive prompt for course generation"""
        
        age_min, age_max = target_age_range
        
        return f"""
        You are an expert educational content creator. Analyze the following textbook content and create a comprehensive, structured course.

        TEXTBOOK CONTENT:
        {textbook_content[:4000]}... # Truncated for prompt efficiency

        COURSE REQUIREMENTS:
        - Title: {course_title}
        - Subject: {subject}
        - Target Age: {age_min}-{age_max} years
        - Duration: {total_weeks} weeks
        - Structure: {blocks_per_week} blocks per week
        - Difficulty: {difficulty_level}

        Create a JSON response with this exact structure:
        {{
            "title": "{course_title}",
            "subject": "{subject}",
            "description": "Comprehensive course description (2-3 sentences)",
            "age_min": {age_min},
            "age_max": {age_max},
            "difficulty_level": "{difficulty_level}",
            "total_weeks": {total_weeks},
            "blocks_per_week": {blocks_per_week},
            "textbook_source": "Source textbook information",
            "blocks": [
                {{
                    "week": 1,
                    "block_number": 1,
                    "title": "Block title",
                    "description": "What this block covers",
                    "learning_objectives": ["Objective 1", "Objective 2", "Objective 3"],
                    "content": "Detailed lesson content from textbook (200-400 words)",
                    "duration_minutes": 45,
                    "resources": [
                        {{"type": "article", "title": "Resource Title", "url": "placeholder_url", "search_query": "specific search terms"}},
                        {{"type": "video", "title": "Video Title", "url": "placeholder_url", "search_query": "YouTube search terms"}},
                        {{"type": "interactive", "title": "Activity Title", "url": "placeholder_url", "search_query": "educational resource search"}}
                    ],
                    "assignments": [
                        {{
                            "title": "Assignment Title",
                            "description": "Assignment description",
                            "type": "homework|quiz|project|assessment",
                            "duration_minutes": 30,
                            "points": 100,
                            "rubric": "Grading criteria",
                            "due_days_after_block": 3
                        }}
                    ]
                }}
            ],
            "overall_assignments": [
                {{
                    "title": "Midterm Assessment",
                    "description": "Comprehensive assessment covering weeks 1-{total_weeks//2}",
                    "type": "assessment",
                    "week_assigned": {total_weeks//2},
                    "duration_minutes": 60,
                    "points": 200,
                    "rubric": "Comprehensive rubric",
                    "due_days_after_assignment": 7
                }}
            ]
        }}

        IMPORTANT GUIDELINES:
        1. Base ALL content on the provided textbook
        2. Create {total_weeks * blocks_per_week} blocks total
        3. Each block should have 2-4 learning objectives
        4. Include varied resource types (articles, videos, interactive content)
        5. Create realistic search queries for finding resources
        6. Assignments should test understanding of block content
        7. Progress logically through the textbook material
        8. Ensure age-appropriate language and complexity
        9. Include hands-on activities and real-world applications
        10. Create assessment rubrics that are specific and measurable

        Generate comprehensive, detailed content that will create an engaging learning experience.
        """

    def _create_course_generation_prompt_for_file(
        self, uploaded_file, course_title: str, subject: str, 
        target_age_range: tuple, total_weeks: int, blocks_per_week: int, difficulty_level: str
    ) -> str:
        """Create a comprehensive prompt for course generation from uploaded files"""
        
        age_min, age_max = target_age_range
        
        return f"""
        You are an expert educational content creator with multimodal analysis capabilities. 
        Analyze the uploaded textbook file comprehensively and create a structured course.
        
        📚 **MULTIMODAL ANALYSIS INSTRUCTIONS:**
        - Read ALL text content from the document (including text in images)
        - Analyze any images, diagrams, charts, or visual content
        - Extract information from tables, figures, and captions
        - Understand the document structure and organization
        - Process any embedded media or visual elements
        - Handle scanned pages or image-based text
        
        🎯 **COURSE REQUIREMENTS:**
        - Title: {course_title}
        - Subject: {subject}
        - Target Age: {age_min}-{age_max} years
        - Duration: {total_weeks} weeks
        - Structure: {blocks_per_week} blocks per week
        - Difficulty: {difficulty_level}

        📖 **CONTENT ANALYSIS GUIDELINES:**
        1. Extract key concepts from ALL content (text + visual)
        2. Identify chapter/section structure from the document
        3. Recognize learning progression and dependencies
        4. Note any visual examples, diagrams, or illustrations
        5. Extract exercises, examples, and practice problems
        6. Understand the pedagogical approach used
        7. Identify vocabulary and key terms
        8. Note any assessment criteria or evaluation methods

        Create a JSON response with this exact structure:
        {{
            "title": "{course_title}",
            "subject": "{subject}",
            "description": "Comprehensive course description based on the analyzed content (2-3 sentences)",
            "age_min": {age_min},
            "age_max": {age_max},
            "difficulty_level": "{difficulty_level}",
            "total_weeks": {total_weeks},
            "blocks_per_week": {blocks_per_week},
            "textbook_source": "Information extracted from the document metadata and content",
            "blocks": [
                {{
                    "week": 1,
                    "block_number": 1,
                    "title": "Block title derived from textbook content",
                    "description": "What this block covers based on the source material",
                    "learning_objectives": ["Objective 1 from content", "Objective 2 from content", "Objective 3 from content"],
                    "content": "Detailed lesson content extracted and synthesized from textbook (300-500 words)",
                    "duration_minutes": 45,
                    "visual_elements": ["Description of relevant images/diagrams", "Charts or tables referenced"],
                    "resources": [
                        {{"type": "article", "title": "Resource Title", "url": "placeholder_url", "search_query": "specific search terms based on content"}},
                        {{"type": "video", "title": "Video Title", "url": "placeholder_url", "search_query": "YouTube search terms for topic"}},
                        {{"type": "interactive", "title": "Activity Title", "url": "placeholder_url", "search_query": "educational resource search"}}
                    ],
                    "assignments": [
                        {{
                            "title": "Assignment Title based on content",
                            "description": "Assignment description derived from textbook exercises",
                            "type": "homework|quiz|project|assessment",
                            "duration_minutes": 30,
                            "points": 100,
                            "rubric": "Grading criteria based on textbook standards",
                            "due_days_after_block": 3
                        }}
                    ]
                }}
            ],
            "overall_assignments": [
                {{
                    "title": "Comprehensive Assessment",
                    "description": "Assessment covering material from the analyzed textbook",
                    "type": "assessment",
                    "week_assigned": {total_weeks//2},
                    "duration_minutes": 60,
                    "points": 200,
                    "rubric": "Comprehensive rubric based on textbook evaluation methods",
                    "due_days_after_assignment": 7
                }}
            ],
            "document_insights": {{
                "total_pages_analyzed": "Number of pages processed",
                "visual_elements_found": "Count of images/diagrams/charts",
                "main_topics_identified": ["Topic 1", "Topic 2", "Topic 3"],
                "complexity_indicators": ["Vocabulary level", "Concept difficulty", "Prerequisites"]
            }}
        }}

        🔍 **ADVANCED PROCESSING REQUIREMENTS:**
        1. Base ALL content on the uploaded document - extract from text AND images
        2. Create {total_weeks * blocks_per_week} blocks total
        3. Each block should have 2-4 learning objectives derived from content
        4. Include information about visual elements found in the document
        5. Reference specific sections, chapters, or page content
        6. Create assignments based on exercises found in the textbook
        7. Progress logically through the document's organization
        8. Ensure age-appropriate language while preserving academic content
        9. Include hands-on activities inspired by textbook examples
        10. Create assessment rubrics that align with textbook standards

        📊 **MULTIMODAL PROCESSING:**
        - Extract text from images using OCR capabilities
        - Understand diagrams and their educational context
        - Process mathematical equations and formulas
        - Analyze charts, graphs, and data visualizations
        - Interpret scientific illustrations and technical drawings
        - Read text from screenshots or scanned pages

        Generate comprehensive, detailed content that fully utilizes the multimodal analysis of the uploaded textbook file.
        """

    async def _enhance_course_with_resources(self, course_data: Dict) -> Dict:
        """
        Enhance the course with actual resource links using search queries
        """
        enhanced_course = course_data.copy()
        
        # Process each block to find actual resources
        for block in enhanced_course["blocks"]:
            enhanced_resources = []
            
            for resource in block["resources"]:
                if resource["type"] == "video":
                    # Generate YouTube search URL
                    search_query = resource.get("search_query", resource["title"])
                    youtube_url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
                    resource["url"] = youtube_url
                    
                elif resource["type"] == "article":
                    # Generate Google search URL for educational articles
                    search_query = resource.get("search_query", resource["title"])
                    search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}+educational+article"
                    resource["url"] = search_url
                    
                elif resource["type"] == "interactive":
                    # Generate search for interactive educational content
                    search_query = resource.get("search_query", resource["title"])
                    interactive_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}+interactive+educational+tool"
                    resource["url"] = interactive_url
                
                enhanced_resources.append(resource)
            
            block["resources"] = enhanced_resources
        
        return enhanced_course

    async def generate_youtube_links(self, topic: str, count: int = 3) -> List[Dict[str, str]]:
        """
        Generate YouTube search links for educational content
        """
        search_variations = [
            f"{topic} educational tutorial",
            f"{topic} explained simply", 
            f"learn {topic} step by step",
            f"{topic} for students",
            f"{topic} crash course"
        ]
        
        links = []
        for i, variation in enumerate(search_variations[:count]):
            links.append({
                "title": f"Educational Video: {topic} ({i+1})",
                "url": f"https://www.youtube.com/results?search_query={variation.replace(' ', '+')}",
                "type": "video",
                "description": f"YouTube search for {variation}"
            })
        
        return links

    async def generate_article_links(self, topic: str, subject: str, count: int = 3) -> List[Dict[str, str]]:
        """
        Generate educational article search links
        """
        search_variations = [
            f"{topic} {subject} educational article",
            f"{topic} explained {subject}",
            f"learn about {topic} {subject}"
        ]
        
        links = []
        for i, variation in enumerate(search_variations[:count]):
            links.append({
                "title": f"Article: {topic} in {subject} ({i+1})",
                "url": f"https://www.google.com/search?q={variation.replace(' ', '+')}",
                "type": "article",
                "description": f"Educational article search for {variation}"
            })
        
        return links

    async def create_assignment_from_content(self, content: str, block_title: str, learning_objectives: List[str]) -> Dict[str, Any]:
        """
        Create a detailed assignment based on lesson content
        """
        assignment_prompt = f"""
        Create a detailed assignment based on this lesson content:
        
        BLOCK TITLE: {block_title}
        LEARNING OBJECTIVES: {', '.join(learning_objectives)}
        CONTENT: {content[:1000]}...
        
        Generate a JSON assignment with this structure:
        {{
            "title": "Assignment title",
            "description": "Detailed assignment description (what students need to do)",
            "type": "homework",
            "instructions": "Step-by-step instructions",
            "duration_minutes": 45,
            "points": 100,
            "rubric": "Detailed grading rubric with criteria",
            "due_days_after_block": 3,
            "submission_format": "What format students should submit (PDF, document, etc.)",
            "learning_outcomes": ["What students will demonstrate", "Skills they'll practice"]
        }}
        
        Make the assignment engaging, practical, and directly related to the learning objectives.
        """
        
        try:
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                assignment_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.6,
                    max_output_tokens=1024,
                    response_mime_type="application/json"
                )
            )
            
            return json.loads(response.text)
            
        except Exception as e:
            # Fallback assignment if generation fails
            return {
                "title": f"Assignment: {block_title}",
                "description": f"Complete exercises related to {block_title}",
                "type": "homework",
                "instructions": "Follow the lesson content and complete all exercises.",
                "duration_minutes": 30,
                "points": 100,
                "rubric": "Completion (50%), Accuracy (30%), Understanding (20%)",
                "due_days_after_block": 3,
                "submission_format": "PDF document",
                "learning_outcomes": learning_objectives[:2]
            }

    async def grade_submission(
        self,
        submission_content: str,
        assignment_title: str,
        assignment_description: str,
        rubric: str,
        max_points: int = 100,
        submission_type: str = "homework"
    ) -> Dict[str, Any]:
        """
        Grade a student submission using Gemini AI
        
        This comprehensive grading function provides:
        - Detailed feedback and corrections
        - Numeric scoring based on rubric
        - Strengths and improvement areas
        - Specific recommendations for better performance
        """
        
        grading_prompt = f"""
        You are an expert educational assessor. Grade this student submission with detailed analysis.

        ASSIGNMENT DETAILS:
        Title: {assignment_title}
        Description: {assignment_description}
        Type: {submission_type}
        Maximum Points: {max_points}
        
        GRADING RUBRIC:
        {rubric}
        
        STUDENT SUBMISSION:
        {submission_content}
        
        Provide a comprehensive assessment in JSON format:
        {{
            "score": 85,
            "percentage": 85.0,
            "grade_letter": "B+",
            "overall_feedback": "Comprehensive overall assessment of the work",
            "detailed_feedback": "Detailed analysis of strengths and weaknesses",
            "strengths": [
                "Specific strength 1",
                "Specific strength 2", 
                "Specific strength 3"
            ],
            "improvements": [
                "Specific area for improvement 1",
                "Specific area for improvement 2",
                "Specific area for improvement 3"
            ],
            "corrections": [
                "Specific correction or error found",
                "Another correction needed",
                "Additional feedback point"
            ],
            "rubric_breakdown": {{
                "criteria_1": {{"score": 20, "max": 25, "feedback": "Specific feedback"}},
                "criteria_2": {{"score": 18, "max": 25, "feedback": "Specific feedback"}},
                "criteria_3": {{"score": 22, "max": 25, "feedback": "Specific feedback"}},
                "criteria_4": {{"score": 25, "max": 25, "feedback": "Specific feedback"}}
            }},
            "recommendations": [
                "Specific recommendation for future work",
                "Study suggestion or resource",
                "Practice activity suggestion"
            ],
            "time_spent_minutes": 15,
            "effort_level": "high|medium|low",
            "understanding_demonstrated": "excellent|good|fair|needs_improvement"
        }}
        
        GRADING GUIDELINES:
        1. Be thorough but constructive in feedback
        2. Provide specific examples from the submission
        3. Score fairly based on the rubric criteria
        4. Offer actionable improvement suggestions
        5. Recognize effort and good attempts even if incorrect
        6. Be encouraging while maintaining academic standards
        7. Focus on learning outcomes and skill development
        """
        
        try:
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                grading_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.3,  # Lower temperature for more consistent grading
                    max_output_tokens=2048,
                    response_mime_type="application/json"
                )
            )
            
            grade_result = json.loads(response.text)
            
            # Ensure score consistency
            if "score" in grade_result and "percentage" not in grade_result:
                grade_result["percentage"] = (grade_result["score"] / max_points) * 100
            
            # Add metadata
            grade_result["graded_by"] = "Gemini AI"
            grade_result["graded_at"] = datetime.utcnow().isoformat()
            grade_result["max_points"] = max_points
            
            return grade_result
            
        except Exception as e:
            # Fallback grading if AI fails
            return {
                "score": max_points * 0.7,  # Default to 70%
                "percentage": 70.0,
                "grade_letter": "C+",
                "overall_feedback": "Submission received and reviewed. AI grading temporarily unavailable.",
                "detailed_feedback": f"Error in AI grading: {str(e)}. Please review manually.",
                "strengths": ["Submission completed on time"],
                "improvements": ["AI grading unavailable - please consult instructor"],
                "corrections": [],
                "recommendations": ["Resubmit when AI grading is available"],
                "graded_by": "Fallback System",
                "graded_at": datetime.utcnow().isoformat(),
                "max_points": max_points,
                "error": str(e)
            }

    async def grade_bulk_submissions(
        self,
        submissions: List[Dict[str, Any]],
        assignment_title: str,
        assignment_description: str,
        rubric: str,
        max_points: int = 100
    ) -> Dict[str, Any]:
        """
        Grade multiple student submissions in bulk using Gemini AI
        
        This function efficiently processes multiple submissions while maintaining
        individual detailed feedback for each student.
        """
        
        print(f"🤖 Starting bulk Gemini AI grading for {len(submissions)} submissions")
        
        grading_results = []
        successful_grades = 0
        failed_grades = 0
        
        for i, submission in enumerate(submissions):
            try:
                print(f"📝 Grading submission {i+1}/{len(submissions)}: {submission.get('student_name', 'Unknown')}")
                
                # Grade individual submission
                grade_result = await self.grade_submission(
                    submission_content=submission.get("content", "No content provided"),
                    assignment_title=assignment_title,
                    assignment_description=assignment_description,
                    rubric=rubric,
                    max_points=max_points,
                    submission_type=submission.get("submission_type", "homework")
                )
                
                # Add submission metadata
                grade_result.update({
                    "submission_id": submission.get("submission_id"),
                    "user_id": submission.get("user_id"),
                    "student_name": submission.get("student_name", "Unknown"),
                    "success": True
                })
                
                grading_results.append(grade_result)
                successful_grades += 1
                
                # Add small delay to avoid rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Failed to grade submission for {submission.get('student_name', 'Unknown')}: {str(e)}")
                
                # Add failed submission to results
                grading_results.append({
                    "submission_id": submission.get("submission_id"),
                    "user_id": submission.get("user_id"), 
                    "student_name": submission.get("student_name", "Unknown"),
                    "success": False,
                    "error": str(e),
                    "score": 0,
                    "percentage": 0.0,
                    "overall_feedback": "Grading failed due to technical error"
                })
                failed_grades += 1
        
        # Create batch summary
        batch_summary = {
            "total_submissions": len(submissions),
            "successfully_graded": successful_grades,
            "failed_grades": failed_grades,
            "success_rate": (successful_grades / len(submissions)) * 100 if submissions else 0,
            "average_score": None,
            "grade_distribution": {}
        }
        
        # Calculate statistics for successful grades
        successful_results = [r for r in grading_results if r.get("success", False)]
        if successful_results:
            scores = [r["percentage"] for r in successful_results]
            batch_summary["average_score"] = sum(scores) / len(scores)
            
            # Grade distribution
            grade_ranges = {"A (90-100)": 0, "B (80-89)": 0, "C (70-79)": 0, "D (60-69)": 0, "F (0-59)": 0}
            for score in scores:
                if score >= 90:
                    grade_ranges["A (90-100)"] += 1
                elif score >= 80:
                    grade_ranges["B (80-89)"] += 1
                elif score >= 70:
                    grade_ranges["C (70-79)"] += 1
                elif score >= 60:
                    grade_ranges["D (60-69)"] += 1
                else:
                    grade_ranges["F (0-59)"] += 1
            
            batch_summary["grade_distribution"] = grade_ranges
        
        print(f"✅ Bulk grading complete: {successful_grades}/{len(submissions)} successful")
        
        return {
            "status": "completed",
            "batch_summary": batch_summary,
            "student_results": grading_results,
            "graded_by": "Gemini AI Bulk Processor",
            "processed_at": datetime.utcnow().isoformat()
        }

    async def extract_text_from_pdf_content(self, pdf_content: str) -> str:
        """
        Extract and process text content from PDF for grading
        This is a placeholder - in production you'd use proper PDF processing
        """
        try:
            # For now, assume pdf_content is already text extracted from PDF
            # In production, integrate with proper PDF text extraction library
            
            if not pdf_content or len(pdf_content.strip()) < 10:
                return "No readable content found in submission"
            
            # Clean up the content
            cleaned_content = re.sub(r'\s+', ' ', pdf_content)  # Normalize whitespace
            cleaned_content = cleaned_content.strip()
            
            # Limit content length for processing
            if len(cleaned_content) > 5000:
                cleaned_content = cleaned_content[:5000] + "... [Content truncated for processing]"
            
            return cleaned_content
            
        except Exception as e:
            return f"Error extracting content from PDF: {str(e)}"

    async def analyze_assignment_difficulty(
        self,
        assignment_description: str,
        target_age: int,
        subject: str
    ) -> Dict[str, Any]:
        """
        Analyze assignment difficulty and suggest improvements
        """
        
        analysis_prompt = f"""
        Analyze this assignment for appropriateness and difficulty level.
        
        ASSIGNMENT: {assignment_description}
        TARGET AGE: {target_age}
        SUBJECT: {subject}
        
        Provide analysis in JSON format:
        {{
            "difficulty_level": "beginner|intermediate|advanced",
            "age_appropriate": true,
            "estimated_completion_time": 45,
            "cognitive_load": "low|medium|high",
            "suggestions": [
                "Specific improvement suggestion",
                "Another helpful tip"
            ],
            "strengths": [
                "What works well in this assignment"
            ],
            "potential_challenges": [
                "What students might struggle with"
            ]
        }}
        """
        
        try:
            response = await asyncio.to_thread(
                self.config.model.generate_content,
                analysis_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.4,
                    max_output_tokens=1024,
                    response_mime_type="application/json"
                )
            )
            
            return json.loads(response.text)
            
        except Exception as e:
            return {
                "difficulty_level": "intermediate",
                "age_appropriate": True,
                "estimated_completion_time": 30,
                "cognitive_load": "medium",
                "suggestions": ["AI analysis unavailable"],
                "strengths": ["Assignment created successfully"],
                "potential_challenges": [f"Analysis error: {str(e)}"]
            }

    async def upload_file_to_gemini(self, file_content: bytes, filename: str, mime_type: str = None) -> str:
        """
        Upload file directly to Gemini using the File API for native processing
        This allows Gemini to read PDFs with images, scanned documents, and mixed content directly
        """
        try:
            import tempfile
            
            # Determine MIME type if not provided
            if not mime_type:
                file_extension = Path(filename).suffix.lower()
                mime_types = {
                    '.pdf': 'application/pdf',
                    '.txt': 'text/plain',
                    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                    '.doc': 'application/msword',
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.gif': 'image/gif',
                    '.webp': 'image/webp'
                }
                mime_type = mime_types.get(file_extension, 'application/octet-stream')
            
            # Create temporary file for Gemini upload
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as temp_file:
                temp_file.write(file_content)
                temp_file_path = temp_file.name
            
            try:
                # Upload file to Gemini
                print(f"📤 Uploading {filename} to Gemini AI for native processing...")
                uploaded_file = genai.upload_file(path=temp_file_path, display_name=filename)
                
                print(f"✅ File uploaded successfully: {uploaded_file.name}")
                print(f"📋 MIME type: {uploaded_file.mime_type}")
                print(f"📊 File size: {uploaded_file.size_bytes} bytes")
                
                # Wait for file processing to complete
                import time
                while uploaded_file.state.name == "PROCESSING":
                    print("⏳ Waiting for file processing...")
                    time.sleep(2)
                    uploaded_file = genai.get_file(uploaded_file.name)
                
                if uploaded_file.state.name == "FAILED":
                    raise Exception(f"File processing failed: {uploaded_file.error}")
                
                print(f"🎉 File processing complete! State: {uploaded_file.state.name}")
                return uploaded_file.name  # Return the file URI for Gemini
                
            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)
                
        except Exception as e:
            raise Exception(f"Error uploading file '{filename}' to Gemini: {str(e)}")

    async def process_uploaded_textbook_file(self, file_content: bytes, filename: str) -> str:
        """
        Process uploaded textbook file using Gemini's native capabilities
        Returns the Gemini file URI for direct use in prompts
        
        This method leverages Gemini's multimodal capabilities to:
        - Read PDFs with images and scanned content
        - Process Word documents with embedded media
        - Handle mixed content (text + images)
        - Extract text from image-based documents
        """
        try:
            # Get file extension and validate
            file_extension = Path(filename).suffix.lower()
            
            # For text files, we can still extract content directly for faster processing
            if file_extension == '.txt' and len(file_content) < 100000:  # < 100KB
                try:
                    text_content = file_content.decode('utf-8', errors='ignore')
                    if len(text_content.strip()) >= 100:
                        print(f"📝 Processing text file directly: {len(text_content)} characters")
                        return text_content
                except UnicodeDecodeError:
                    pass  # Fall through to Gemini processing
            
            # For all other files or large text files, use Gemini's native processing
            print(f"🤖 Using Gemini native processing for {filename}")
            gemini_file_uri = await self.upload_file_to_gemini(file_content, filename)
            
            # Return a special marker that indicates this is a Gemini file reference
            return f"GEMINI_FILE_URI:{gemini_file_uri}"
            
        except Exception as e:
            raise Exception(f"Error processing file '{filename}': {str(e)}")

    def validate_textbook_file(self, filename: str, file_size: int) -> Dict[str, Any]:
        """
        Validate uploaded textbook file for Gemini native processing
        Supports documents, images, and multimodal content
        """
        # File size limit (20MB for Gemini processing)
        MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB (increased for native processing)
        
        # Allowed file types - expanded for Gemini's multimodal capabilities
        ALLOWED_EXTENSIONS = {
            # Document formats
            '.txt', '.pdf', '.doc', '.docx',
            # Image formats (for textbook pages, diagrams, etc.)
            '.png', '.jpg', '.jpeg', '.gif', '.webp'
        }
        
        file_extension = Path(filename).suffix.lower()
        
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "file_type": file_extension,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "processing_method": "gemini_native"
        }
        
        # Check file size
        if file_size > MAX_FILE_SIZE:
            validation_result["valid"] = False
            validation_result["errors"].append(f"File size ({validation_result['size_mb']}MB) exceeds maximum allowed size (20MB)")
        
        # Check file extension
        if file_extension not in ALLOWED_EXTENSIONS:
            validation_result["valid"] = False
            validation_result["errors"].append(f"File type '{file_extension}' not supported. Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}")
        
        # Informational messages for different file types
        if file_extension == '.pdf':
            validation_result["warnings"].append("PDF will be processed using Gemini's native capabilities - supports text, images, and scanned content")
        elif file_extension in ['.doc', '.docx']:
            validation_result["warnings"].append("Word document will be processed natively - supports embedded images and complex formatting")
        elif file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.webp']:
            validation_result["warnings"].append("Image file will be processed using Gemini's OCR and visual analysis capabilities")
            validation_result["file_category"] = "image"
        elif file_extension == '.txt':
            validation_result["warnings"].append("Text file will be processed directly for optimal performance")
            validation_result["file_category"] = "text"
        
        return validation_result

# Singleton instance
gemini_service = GeminiService()