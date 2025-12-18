# Bulk Image Upload API Documentation

## New Bulk Upload Endpoint

### POST /bulk-upload-to-pdf

**Description**: Upload multiple images for a specific student assignment and combine them into a single PDF

**Form Data Parameters**:
- `assignment_id`: Integer (required) - The assignment ID
- `student_id`: Integer (required) - The student ID  
- `files`: Multiple files (required) - Image files to upload

**Example Usage with Swagger**:

1. **Form Data Fields**:
   ```
   assignment_id: 1
   student_id: 5
   ```

2. **Files**: Select multiple image files (JPG, PNG, GIF, BMP, TIFF, WEBP)

**Response**: Returns the generated PDF file with headers:
- `X-Total-Images`: Number of images processed
- `X-Student-Name`: Student's full name
- `X-Assignment-Title`: Assignment title
- `X-PDF-ID`: Database ID of the PDF record

## Supporting Endpoints

### GET /bulk-upload/assignment/{assignment_id}/students
**Description**: Get list of students for an assignment to choose from for bulk upload

**Example**: `/bulk-upload/assignment/1/students`

### GET /bulk-upload/assignment/{assignment_id}/student/{student_id}/pdf
**Description**: Download existing PDF for a student assignment

**Example**: `/bulk-upload/assignment/1/student/5/pdf`

### DELETE /bulk-upload/assignment/{assignment_id}/student/{student_id}/pdf
**Description**: Delete PDF for a student assignment

**Example**: `/bulk-upload/assignment/1/student/5/pdf`

### GET /bulk-upload/health
**Description**: Health check for the bulk upload service

## Integration with Existing Workflow

The new bulk upload endpoints integrate seamlessly with the existing assignment and grading workflow:

1. **Teacher uploads images**: Uses the new bulk upload endpoint with assignment and student selection
2. **PDF generation**: Images are automatically combined into a PDF and saved to the database
3. **Grading workflow**: Existing grading session endpoints can be used to grade the generated PDFs
4. **Grade sync**: Grades automatically sync with the existing grade management system

## Key Features

- ✅ **Assignment-based**: Requires assignment and student selection
- ✅ **Database integration**: PDFs are saved in the StudentPDF table
- ✅ **No OCR processing**: Images are combined as-is without text extraction
- ✅ **Automatic naming**: PDF files are named with student name and assignment title
- ✅ **Replace functionality**: New uploads replace existing PDFs for the same student/assignment
- ✅ **Teacher access control**: Only teachers can upload for their assignments
- ✅ **Student validation**: Ensures students are enrolled in the assignment's subject

## Workflow Example

1. Teacher selects assignment from their subjects
2. Teacher selects student from assignment's enrolled students  
3. Teacher uploads multiple images for that student's assignment
4. System combines images into PDF with proper naming
5. PDF is saved in database and linked to assignment/student
6. Teacher can proceed with grading using existing grading endpoints
