# Example of how to integrate both routers in your main FastAPI application

from fastapi import FastAPI
from Endpoints import study_area, grades

app = FastAPI(
    title="BrainInk Education Platform API",
    description="API for managing schools, students, teachers, subjects, assignments, and grades",
    version="1.0.0"
)

# Include both routers with appropriate prefixes
app.include_router(
    study_area.router, 
    prefix="/api/v1/study-area",
    tags=["Study Area Management"]
)

app.include_router(
    grades.router,
    prefix="/api/v1/grades",
    tags=["Assignments & Grades"]
)

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "BrainInk Education Platform API is running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
