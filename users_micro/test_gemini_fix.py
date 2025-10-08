"""
Quick Test Script for Gemini Grading Fix
==========================================

Run this script to verify Gemini can now properly grade student work
without safety filter blocks.

Usage:
    python test_gemini_fix.py path/to/test_image.jpg
"""

import sys
import asyncio
from pathlib import Path

async def test_gemini_grading():
    """Test if Gemini safety settings are working"""
    
    print("🧪 Testing Gemini Grading with Safety Settings Fix")
    print("=" * 60)
    
    # Import the service
    try:
        from services.gemini_service import gemini_service
        print("✅ Successfully imported gemini_service")
    except Exception as e:
        print(f"❌ Failed to import: {e}")
        return False
    
    # Check if safety settings method exists and works
    try:
        safety_settings = gemini_service._default_safety_settings()
        print(f"✅ Safety settings loaded: {len(safety_settings)} categories configured")
        print(f"   Settings: {list(safety_settings.keys())}")
    except Exception as e:
        print(f"❌ Safety settings error: {e}")
        return False
    
    # Test with sample text
    test_content = """
    My Story About Health
    
    Today I learned about keeping my body healthy. I eat vegetables and fruits.
    I also exercise every day by playing outside with my friends. Sometimes I feel
    sad when I'm tired, but I always feel better after I rest.
    
    The End.
    """
    
    print("\n📝 Testing with sample student writing...")
    print(f"   Content: {test_content[:100]}...")
    
    try:
        result = await gemini_service.grade_submission(
            submission_content=test_content,
            assignment_title="My Health Story",
            assignment_description="Write a short story about staying healthy",
            rubric="Check for creativity, grammar, and relevance to health topics",
            submission_type="homework",
            max_points=100
        )
        
        score = result.get("score") or result.get("percentage")
        feedback = result.get("overall_feedback") or result.get("feedback")
        
        print(f"\n✅ Grading succeeded!")
        print(f"   Score: {score}")
        print(f"   Feedback length: {len(str(feedback)) if feedback else 0} chars")
        print(f"   Has feedback: {bool(feedback)}")
        
        if score is not None and score > 0:
            print(f"\n🎉 SUCCESS! Gemini returned a valid score: {score}")
            return True
        elif "error" in str(result).lower() or "harm_category" in str(result).lower():
            print(f"\n❌ FAILED! Still getting safety blocks:")
            print(f"   Result: {result}")
            return False
        else:
            print(f"\n⚠️  Score is 0 or null. Check result:")
            print(f"   {result}")
            return False
            
    except Exception as e:
        print(f"\n❌ Grading failed with error: {e}")
        return False

if __name__ == "__main__":
    print("\n" + "="*60)
    print("GEMINI GRADING FIX VERIFICATION TEST")
    print("="*60 + "\n")
    
    result = asyncio.run(test_gemini_grading())
    
    print("\n" + "="*60)
    if result:
        print("✅ TEST PASSED - Gemini is working correctly!")
        print("   You can now submit assignments and get proper grades.")
    else:
        print("❌ TEST FAILED - There may still be issues")
        print("   Check the errors above and verify:")
        print("   1. Gemini API key is set correctly")
        print("   2. Safety settings are uncommented")
        print("   3. generate_content calls include safety_settings parameter")
    print("="*60 + "\n")
    
    sys.exit(0 if result else 1)
