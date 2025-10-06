"""
API endpoint to populate reading content remotely
Add this to your reading_assistant.py endpoints file
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from db.database import get_db
from models.reading_assistant_models import ReadingContent, ReadingLevel, DifficultyLevel
from services.reading_assistant_service import ReadingAssistantService

router = APIRouter()

# Import the enhanced content
from utils.populate_enhanced_reading_content import ENHANCED_CONTENT, _calculate_complexity_score


@router.post("/admin/populate-reading-content")
async def populate_reading_content_endpoint(
    clear_existing: bool = False,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Admin endpoint to populate reading content
    
    Query Parameters:
    - clear_existing: If true, deletes all existing content first
    """
    
    try:
        if clear_existing:
            deleted_count = db.query(ReadingContent).delete()
            db.commit()
            print(f"🗑️  Deleted {deleted_count} existing content items")
        
        content_count = 0
        added_titles = []
        
        for reading_level, difficulty_dict in ENHANCED_CONTENT.items():
            for difficulty_level, content_list in difficulty_dict.items():
                for content_data in content_list:
                    
                    # Check if this title already exists
                    existing = db.query(ReadingContent).filter_by(
                        title=content_data["title"]
                    ).first()
                    
                    if existing and not clear_existing:
                        print(f"⏭️  Skipping '{content_data['title']}' (already exists)")
                        continue
                    
                    # Calculate metrics
                    word_count = len(content_data["content"].split())
                    estimated_time = word_count * 2  # 2 seconds per word
                    
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
                        created_by=1,  # System user
                        is_active=True
                    )
                    
                    db.add(new_content)
                    content_count += 1
                    added_titles.append(content_data["title"])
        
        db.commit()
        
        # Get summary by level
        summary = {}
        for reading_level in ReadingLevel:
            count = db.query(ReadingContent).filter_by(reading_level=reading_level).count()
            summary[reading_level.value] = count
        
        total = db.query(ReadingContent).count()
        
        return {
            "success": True,
            "message": f"Successfully added {content_count} new reading passages",
            "added_count": content_count,
            "added_titles": added_titles,
            "total_in_database": total,
            "summary_by_level": summary
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to populate content: {str(e)}"
        )


# Add this endpoint to see current content
@router.get("/admin/reading-content-stats")
async def get_content_stats(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Get statistics about reading content in database"""
    
    summary = {}
    for reading_level in ReadingLevel:
        count = db.query(ReadingContent).filter_by(reading_level=reading_level).count()
        summary[reading_level.value] = count
    
    total = db.query(ReadingContent).count()
    
    # Get some sample titles per level
    samples = {}
    for reading_level in ReadingLevel:
        content_items = db.query(ReadingContent).filter_by(
            reading_level=reading_level
        ).limit(5).all()
        samples[reading_level.value] = [item.title for item in content_items]
    
    return {
        "total_content_items": total,
        "by_reading_level": summary,
        "sample_titles": samples
    }
