import httpx
import os
import json
import asyncio
import enum
import uuid
from typing import List, Dict, Any, Optional
from pathlib import Path
import base64
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated
from pydantic import BaseModel

from db.connection import db_dependency
from Endpoints.auth import get_current_user

# Create router for KANA service endpoints
router = APIRouter(tags=["KANA AI Service"])
user_dependency = Annotated[dict, Depends(get_current_user)]

# Pydantic models for API endpoints
class PDFGenerationRequest(BaseModel):
    image_paths: List[str]
    student_name: str
    assignment_title: str
    output_filename: str

class GradingRequest(BaseModel):
    pdf_path: str
    assignment_title: str
    assignment_description: str
    rubric: str
    max_points: int
    feedback_type: str = "detailed"
    student_name: Optional[str] = None

class BatchGradingRequest(BaseModel):
    assignment_data: List[Dict[str, Any]]
    grading_criteria: Dict[str, Any]

class TextExtractionRequest(BaseModel):
    image_paths: List[str]
    language: str = "en"

class QualityAnalysisRequest(BaseModel):
    pdf_path: str
    assignment_criteria: Dict[str, Any]

class KanaService:
    """
    Service class to communicate with KANA AI backend for PDF generation and grading
    """
    
    def __init__(self):
        self.base_url = os.getenv("KANA_BASE_URL", "https://kana-backend-app.onrender.com")
        self.timeout = 300  # 5 minutes timeout for AI operations
        
    @staticmethod
    async def generate_assignment_pdf(
        image_paths: List[str],
        student_name: str,
        assignment_title: str,
        output_path: str
    ) -> Dict[str, Any]:
        """
        Generate PDF from multiple assignment images
        
        Args:
            image_paths: List of image file paths
            student_name: Name of the student
            assignment_title: Title of the assignment
            output_path: Where to save the generated PDF
            
        Returns:
            Dictionary with success status and result info
        """
        try:
            kana_service = KanaService()
            
            # Prepare images for upload
            image_data = []
            for img_path in image_paths:
                if not Path(img_path).exists():
                    print(f"Warning: Image not found: {img_path}")
                    continue
                    
                # Convert image to base64
                with open(img_path, "rb") as img_file:
                    img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                    img_name = Path(img_path).name
                    
                image_data.append({
                    "filename": img_name,
                    "data": img_base64,
                    "path": img_path
                })
            
            if not image_data:
                return {
                    "success": False,
                    "error": "No valid images found for PDF generation"
                }
            
            # Prepare request payload
            payload = {
                "operation": "generate_assignment_pdf",
                "data": {
                    "student_name": student_name,
                    "assignment_title": assignment_title,
                    "images": image_data,
                    "output_filename": Path(output_path).name,
                    "metadata": {
                        "created_at": datetime.now().isoformat(),
                        "image_count": len(image_data),
                        "assignment_info": {
                            "title": assignment_title,
                            "student": student_name
                        }
                    }
                }
            }
            
            # Make request to KANA service
            async with httpx.AsyncClient(timeout=kana_service.timeout) as client:
                response = await client.post(
                    f"{kana_service.base_url}/generate-pdf",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get("success", False):
                        # Download the generated PDF
                        pdf_data = base64.b64decode(result.get("pdf_data", ""))
                        
                        # Save PDF to specified path
                        os.makedirs(Path(output_path).parent, exist_ok=True)
                        with open(output_path, "wb") as pdf_file:
                            pdf_file.write(pdf_data)
                        
                        return {
                            "success": True,
                            "pdf_path": output_path,
                            "pdf_size": len(pdf_data),
                            "image_count": len(image_data),
                            "metadata": result.get("metadata", {})
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "PDF generation failed")
                        }
                else:
                    return {
                        "success": False,
                        "error": f"KANA service error: {response.status_code} - {response.text}"
                    }
                    
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "PDF generation timed out. Please try again."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"PDF generation error: {str(e)}"
            }
    
    @staticmethod
    async def grade_assignment_pdf(
        pdf_path: str,
        assignment_title: str,
        assignment_description: str,
        rubric: str,
        max_points: int,
        feedback_type: str = "detailed",
        student_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Grade an assignment PDF using AI
        
        Args:
            pdf_path: Path to the PDF file
            assignment_title: Title of the assignment
            assignment_description: Description of the assignment
            rubric: Grading rubric
            max_points: Maximum possible points
            feedback_type: Type of feedback (brief, detailed, comprehensive)
            student_name: Name of the student (optional)
            
        Returns:
            Dictionary with grading results
        """
        try:
            kana_service = KanaService()
            
            if not Path(pdf_path).exists():
                return {
                    "success": False,
                    "error": "PDF file not found"
                }
            
            # Convert PDF to base64
            with open(pdf_path, "rb") as pdf_file:
                pdf_base64 = base64.b64encode(pdf_file.read()).decode('utf-8')
            
            # Prepare request payload
            payload = {
                "operation": "grade_assignment",
                "data": {
                    "pdf_data": pdf_base64,
                    "pdf_filename": Path(pdf_path).name,
                    "assignment": {
                        "title": assignment_title,
                        "description": assignment_description,
                        "rubric": rubric,
                        "max_points": max_points
                    },
                    "grading_options": {
                        "feedback_type": feedback_type,
                        "include_suggestions": True,
                        "highlight_errors": True,
                        "provide_examples": feedback_type in ["detailed", "comprehensive"]
                    },
                    "student_info": {
                        "name": student_name or "Anonymous",
                        "submission_date": datetime.now().isoformat()
                    }
                }
            }
            
            # Make request to KANA service
            async with httpx.AsyncClient(timeout=kana_service.timeout) as client:
                response = await client.post(
                    f"{kana_service.base_url}/grade-assignment",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get("success", False):
                        grading_data = result.get("grading", {})
                        
                        return {
                            "success": True,
                            "points_earned": grading_data.get("points_earned", 0),
                            "max_points": max_points,
                            "percentage": grading_data.get("percentage", 0),
                            "feedback": grading_data.get("feedback", ""),
                            "detailed_feedback": grading_data.get("detailed_feedback", {}),
                            "rubric_scores": grading_data.get("rubric_scores", {}),
                            "strengths": grading_data.get("strengths", []),
                            "areas_for_improvement": grading_data.get("areas_for_improvement", []),
                            "suggestions": grading_data.get("suggestions", []),
                            "confidence": grading_data.get("confidence", 85),
                            "processing_time": grading_data.get("processing_time", 0),
                            "ai_model_used": grading_data.get("ai_model", "gemini-pro"),
                            "graded_at": datetime.now().isoformat()
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.get("error", "Grading failed")
                        }
                else:
                    return {
                        "success": False,
                        "error": f"KANA service error: {response.status_code} - {response.text}"
                    }
                    
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": "AI grading timed out. Please try again."
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Grading error: {str(e)}"
            }
    
    @staticmethod
    async def batch_grade_assignments(
        assignment_data: List[Dict[str, Any]],
        grading_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Grade multiple assignments in batch
        
        Args:
            assignment_data: List of assignment data dictionaries
            grading_criteria: Common grading criteria for all assignments
            
        Returns:
            Batch grading results
        """
        try:
            kana_service = KanaService()
            
            # Prepare batch request
            payload = {
                "operation": "batch_grade",
                "data": {
                    "assignments": assignment_data,
                    "criteria": grading_criteria,
                    "batch_options": {
                        "parallel_processing": True,
                        "max_concurrent": 5,
                        "timeout_per_assignment": 60
                    }
                }
            }
            
            # Extended timeout for batch operations
            extended_timeout = kana_service.timeout * 2
            
            async with httpx.AsyncClient(timeout=extended_timeout) as client:
                response = await client.post(
                    f"{kana_service.base_url}/batch-grade",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "success": False,
                        "error": f"Batch grading failed: {response.status_code} - {response.text}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"Batch grading error: {str(e)}"
            }
    
    @staticmethod
    async def extract_text_from_images(
        image_paths: List[str],
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Extract text from images using OCR
        
        Args:
            image_paths: List of image file paths
            language: Language for OCR (default: en)
            
        Returns:
            Extracted text results
        """
        try:
            kana_service = KanaService()
            
            # Prepare images
            image_data = []
            for img_path in image_paths:
                if Path(img_path).exists():
                    with open(img_path, "rb") as img_file:
                        img_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                        image_data.append({
                            "filename": Path(img_path).name,
                            "data": img_base64
                        })
            
            payload = {
                "operation": "extract_text",
                "data": {
                    "images": image_data,
                    "ocr_options": {
                        "language": language,
                        "enhance_quality": True,
                        "detect_tables": True,
                        "detect_handwriting": True
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=kana_service.timeout) as client:
                response = await client.post(
                    f"{kana_service.base_url}/extract-text",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "success": False,
                        "error": f"Text extraction failed: {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"Text extraction error: {str(e)}"
            }
    
    @staticmethod
    async def analyze_assignment_quality(
        pdf_path: str,
        assignment_criteria: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze assignment quality and provide detailed feedback
        
        Args:
            pdf_path: Path to assignment PDF
            assignment_criteria: Quality criteria for analysis
            
        Returns:
            Quality analysis results
        """
        try:
            kana_service = KanaService()
            
            if not Path(pdf_path).exists():
                return {
                    "success": False,
                    "error": "PDF file not found"
                }
            
            with open(pdf_path, "rb") as pdf_file:
                pdf_base64 = base64.b64encode(pdf_file.read()).decode('utf-8')
            
            payload = {
                "operation": "analyze_quality",
                "data": {
                    "pdf_data": pdf_base64,
                    "criteria": assignment_criteria,
                    "analysis_options": {
                        "check_completeness": True,
                        "evaluate_organization": True,
                        "assess_clarity": True,
                        "detect_plagiarism": False,  # Optional feature
                        "provide_suggestions": True
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=kana_service.timeout) as client:
                response = await client.post(
                    f"{kana_service.base_url}/analyze-quality",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "success": False,
                        "error": f"Quality analysis failed: {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"Quality analysis error: {str(e)}"
            }
    
    @staticmethod
    async def generate_grade_report(
        grading_results: List[Dict[str, Any]],
        assignment_info: Dict[str, Any],
        report_type: str = "summary"
    ) -> Dict[str, Any]:
        """
        Generate comprehensive grade reports
        
        Args:
            grading_results: List of individual grading results
            assignment_info: Assignment information
            report_type: Type of report (summary, detailed, analytical)
            
        Returns:
            Generated report data
        """
        try:
            kana_service = KanaService()
            
            payload = {
                "operation": "generate_report",
                "data": {
                    "grading_results": grading_results,
                    "assignment_info": assignment_info,
                    "report_options": {
                        "type": report_type,
                        "include_statistics": True,
                        "include_charts": True,
                        "include_recommendations": True,
                        "format": "json"  # Can be json, pdf, or html
                    }
                }
            }
            
            async with httpx.AsyncClient(timeout=kana_service.timeout) as client:
                response = await client.post(
                    f"{kana_service.base_url}/generate-report",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {
                        "success": False,
                        "error": f"Report generation failed: {response.status_code}"
                    }
                    
        except Exception as e:
            return {
                "success": False,
                "error": f"Report generation error: {str(e)}"
            }
    
    @staticmethod
    async def health_check() -> Dict[str, Any]:
        """
        Check if KANA service is healthy and responsive
        
        Returns:
            Health status
        """
        try:
            kana_service = KanaService()
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(f"{kana_service.base_url}/health")
                
                if response.status_code == 200:
                    return {
                        "success": True,
                        "status": "healthy",
                        "response_time": response.elapsed.total_seconds(),
                        "service_info": response.json()
                    }
                else:
                    return {
                        "success": False,
                        "status": "unhealthy",
                        "error": f"Health check failed: {response.status_code}"
                    }
                    
        except httpx.ConnectError:
            return {
                "success": False,
                "status": "unreachable",
                "error": "Cannot connect to KANA service"
            }
        except Exception as e:
            return {
                "success": False,
                "status": "error",
                "error": f"Health check error: {str(e)}"
            }

# === API ENDPOINTS ===

@router.post("/pdf/generate")
async def generate_pdf_endpoint(
    request: PDFGenerationRequest,
    current_user: user_dependency
):
    """
    API endpoint to generate PDF from images
    """
    try:
        output_path = f"uploads/pdfs/{request.output_filename}"
        result = await KanaService.generate_assignment_pdf(
            image_paths=request.image_paths,
            student_name=request.student_name,
            assignment_title=request.assignment_title,
            output_path=output_path
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PDF generation failed: {str(e)}"
        )

@router.post("/grade/assignment")
async def grade_assignment_endpoint(
    request: GradingRequest,
    current_user: user_dependency
):
    """
    API endpoint to grade an assignment PDF
    """
    try:
        result = await KanaService.grade_assignment_pdf(
            pdf_path=request.pdf_path,
            assignment_title=request.assignment_title,
            assignment_description=request.assignment_description,
            rubric=request.rubric,
            max_points=request.max_points,
            feedback_type=request.feedback_type,
            student_name=request.student_name
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Assignment grading failed: {str(e)}"
        )

@router.post("/grade/batch")
async def batch_grade_endpoint(
    request: BatchGradingRequest,
    current_user: user_dependency
):
    """
    API endpoint for batch grading assignments
    """
    try:
        result = await KanaService.batch_grade_assignments(
            assignment_data=request.assignment_data,
            grading_criteria=request.grading_criteria
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch grading failed: {str(e)}"
        )

@router.post("/text/extract")
async def extract_text_endpoint(
    request: TextExtractionRequest,
    current_user: user_dependency
):
    """
    API endpoint to extract text from images
    """
    try:
        result = await KanaService.extract_text_from_images(
            image_paths=request.image_paths,
            language=request.language
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Text extraction failed: {str(e)}"
        )

@router.post("/analyze/quality")
async def analyze_quality_endpoint(
    request: QualityAnalysisRequest,
    current_user: user_dependency
):
    """
    API endpoint to analyze assignment quality
    """
    try:
        result = await KanaService.analyze_assignment_quality(
            pdf_path=request.pdf_path,
            assignment_criteria=request.assignment_criteria
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Quality analysis failed: {str(e)}"
        )

@router.get("/health")
async def health_check_endpoint():
    """
    API endpoint to check KANA service health
    """
    try:
        result = await KanaService.health_check()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Health check failed: {str(e)}"
        )

# Example usage and testing functions
async def test_kana_service():
    """Test function to verify KANA service functionality"""
    
    print("Testing KANA Service...")
    
    # Test health check
    health = await KanaService.health_check()
    print(f"Health Check: {health}")
    
    # Example test data paths (replace with actual paths for testing)
    test_image_paths = [
        "/path/to/test/image1.jpg",
        "/path/to/test/image2.jpg"
    ]
    
    test_pdf_path = "/path/to/test/assignment.pdf"
    
    # Test PDF generation (only if test images exist)
    if all(Path(p).exists() for p in test_image_paths):
        pdf_result = await KanaService.generate_assignment_pdf(
            image_paths=test_image_paths,
            student_name="Test Student",
            assignment_title="Test Assignment",
            output_path="/tmp/test_output.pdf"
        )
        print(f"PDF Generation: {pdf_result}")
    
    # Test grading (only if test PDF exists)
    if Path(test_pdf_path).exists():
        grade_result = await KanaService.grade_assignment_pdf(
            pdf_path=test_pdf_path,
            assignment_title="Test Assignment",
            assignment_description="This is a test assignment",
            rubric="Test rubric with clear criteria",
            max_points=100,
            feedback_type="detailed"
        )
        print(f"AI Grading: {grade_result}")

if __name__ == "__main__":
    # Run tests
    asyncio.run(test_kana_service())