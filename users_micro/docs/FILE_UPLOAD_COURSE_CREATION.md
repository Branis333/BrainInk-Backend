# File Upload Course Creation Guide

## Overview

The `/after-school/courses/from-textbook` endpoint has been updated to accept file uploads instead of requiring users to paste textbook content. This makes the course creation process much more user-friendly and supports various file formats.

## Supported File Types - Gemini Native Processing

- **PDF** (`.pdf`) - All PDFs including scanned documents, images, and mixed content
- **Text** (`.txt`) - Plain text files
- **Word Document** (`.docx`) - Modern Word documents with embedded images and formatting
- **Legacy Word** (`.doc`) - Microsoft Word documents
- **Images** (`.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`) - Textbook pages, diagrams, screenshots

## Advanced Multimodal Capabilities

- **OCR Processing** - Reads text from images and scanned documents
- **Visual Analysis** - Understands diagrams, charts, and educational illustrations
- **Mixed Content** - Processes documents with text, images, tables, and graphics
- **Scanned Textbooks** - Handles photographed or scanned textbook pages
- **Mathematical Content** - Recognizes equations, formulas, and mathematical notation

## File Limitations

- **Maximum file size:** 20MB (increased for native processing)
- **Content validation:** Automatic through Gemini's multimodal analysis
- **Security:** Native Gemini processing eliminates manual extraction risks

## API Endpoint

```
POST /after-school/courses/from-textbook
Content-Type: multipart/form-data
```

## Request Parameters

### File Upload
- `textbook_file` (required): Upload file containing textbook content

### Course Information
- `title` (required): Course title (1-200 characters)
- `subject` (required): Subject name (1-100 characters) 
- `textbook_source` (optional): Information about the textbook source

### Course Structure
- `total_weeks` (optional): Total duration in weeks (1-52, default: 8)
- `blocks_per_week` (optional): Learning blocks per week (1-5, default: 2)

### Target Audience
- `age_min` (optional): Minimum age (3-16, default: 3)
- `age_max` (optional): Maximum age (3-16, default: 16)
- `difficulty_level` (optional): beginner/intermediate/advanced (default: intermediate)

### Generation Options
- `include_assignments` (optional): Generate assignments automatically (default: true)
- `include_resources` (optional): Generate resource links (default: true)

## Example Usage

### Using cURL

```bash
curl -X POST "http://localhost:8000/after-school/courses/from-textbook" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "textbook_file=@/path/to/your/textbook.pdf" \
  -F "title=Advanced Mathematics Course" \
  -F "subject=Mathematics" \
  -F "textbook_source=University Mathematics Textbook 2023" \
  -F "total_weeks=12" \
  -F "blocks_per_week=3" \
  -F "age_min=14" \
  -F "age_max=18" \
  -F "difficulty_level=advanced" \
  -F "include_assignments=true" \
  -F "include_resources=true"
```

### Using Python requests

```python
import requests

url = "http://localhost:8000/after-school/courses/from-textbook"
headers = {"Authorization": "Bearer YOUR_JWT_TOKEN"}

files = {"textbook_file": open("textbook.pdf", "rb")}
data = {
    "title": "Advanced Mathematics Course",
    "subject": "Mathematics", 
    "textbook_source": "University Mathematics Textbook 2023",
    "total_weeks": 12,
    "blocks_per_week": 3,
    "age_min": 14,
    "age_max": 18,
    "difficulty_level": "advanced",
    "include_assignments": True,
    "include_resources": True
}

response = requests.post(url, headers=headers, files=files, data=data)
course = response.json()
```

### Using JavaScript/FormData

```javascript
const formData = new FormData();
formData.append('textbook_file', fileInput.files[0]);
formData.append('title', 'Advanced Mathematics Course');
formData.append('subject', 'Mathematics');
formData.append('textbook_source', 'University Mathematics Textbook 2023');
formData.append('total_weeks', '12');
formData.append('blocks_per_week', '3');
formData.append('age_min', '14');
formData.append('age_max', '18');
formData.append('difficulty_level', 'advanced');
formData.append('include_assignments', 'true');
formData.append('include_resources', 'true');

fetch('/after-school/courses/from-textbook', {
    method: 'POST',
    headers: {
        'Authorization': 'Bearer ' + token
    },
    body: formData
})
.then(response => response.json())
.then(course => console.log('Course created:', course));
```

## Response Format

The endpoint returns a comprehensive course object including:

- Course metadata (title, subject, description, etc.)
- Generated course blocks with learning objectives
- Assignments with rubrics and due dates
- Resource links (YouTube videos, articles)
- Complete course structure ready for student enrollment

## Error Handling

### File Validation Errors
- File too large (>10MB)
- Unsupported file type
- Corrupted or unreadable file

### Content Validation Errors
- Insufficient text content (<100 characters)
- Text extraction failed
- Invalid course parameters

### Example Error Response

```json
{
    "detail": "File validation failed: File size (15.2MB) exceeds maximum allowed size (10MB)"
}
```

## Best Practices

1. **File Preparation:**
   - Ensure text-based PDFs (not scanned images)
   - Use clear, well-formatted documents
   - Include chapter/section headings for better AI analysis

2. **Course Configuration:**
   - Choose appropriate age ranges for target audience
   - Set realistic week counts and block structures
   - Provide descriptive course titles and subjects

3. **Performance:**
   - Files under 5MB process faster
   - Text files (.txt) have the fastest processing time
   - PDF processing may take longer but provides richer content

## Troubleshooting

### Multimodal Processing
- Gemini natively processes all file types including scanned content
- No need for text-selectable PDFs - OCR handles scanned documents
- Images of textbook pages work as well as original documents
- Mixed content (text + images) is fully supported

### Processing Time
- Large files (>5MB) may take 30-60 seconds to process
- AI generation adds additional 15-30 seconds
- Monitor API response times and implement appropriate timeouts

### File Format Support
- Legacy .doc files have limited support - convert to .docx or .txt
- Binary files will be rejected during validation
- Ensure proper file extensions match actual file types