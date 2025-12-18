// export interface QuizQuestion {
//     id: string;
//     question: string;
//     options: string[];
//     correctAnswer: number;
//     explanation: string;
//     difficulty: 'easy' | 'medium' | 'hard';
//     topic: string;
//     weakness_area: string;
// }

// export interface GeneratedQuiz {
//     id: string;
//     assignment_id: number;
//     student_id: number;
//     title: string;
//     description: string;
//     questions: QuizQuestion[];
//     weakness_areas: string[];
//     created_at: string;
//     attempts: QuizAttempt[];
//     max_attempts: number;
//     time_limit_minutes?: number;
// }

// export interface QuizAttempt {
//     id: string;
//     quiz_id: string;
//     student_id: number;
//     answers: { [questionId: string]: number };
//     score: number;
//     completed_at: string;
//     time_taken_seconds: number;
//     feedback: string;
// }

// export interface KanaQuizRequest {
//     weaknessAreas: string[];
//     subject: string;
//     studentLevel: string;
//     assignmentContext: string;
//     difficulty: 'easy' | 'medium' | 'hard';
// }

// class QuizGeneratorServiceClass {
//     private baseUrl = 'http://localhost:8000';
//     private storageKey = 'generated_quizzes';

//     /**
//      * Get stored quizzes from local storage
//      */
//     private getStoredQuizzes(): Record<string, GeneratedQuiz> {
//         try {
//             const stored = localStorage.getItem(this.storageKey);
//             return stored ? JSON.parse(stored) : {};
//         } catch (error) {
//             console.warn('Failed to parse stored quizzes:', error);
//             return {};
//         }
//     }

//     /**
//      * Generate a quiz based on assignment feedback and weakness areas
//      */
//     public async generateQuizFromAssignment(
//         assignmentId: number,
//         studentId: number,
//         feedback: string,
//         weaknessAreas: string[],
//         subject: string,
//         grade: number
//     ): Promise<GeneratedQuiz | null> {
//         try {
//             console.log('🧠 Generating quiz from assignment feedback...');

//             // Call the backend to generate quiz using Kana AI v2 (with fallback to v1)
//             let response = await fetch(`${this.baseUrl}/study-area/quizzes/generate-with-kana-v2`, {
//                 method: 'POST',
//                 headers: {
//                     'Content-Type': 'application/json',
//                 },
//                 body: JSON.stringify({
//                     assignment_id: assignmentId,
//                     student_id: studentId,
//                     feedback,
//                     weakness_areas: weaknessAreas,
//                     subject,
//                     grade
//                 })
//             });

//             // Fallback to v1 endpoint if v2 is not available
//             if (!response.ok) {
//                 console.log('🔄 V2 endpoint failed, trying V1 fallback...');
//                 response = await fetch(`${this.baseUrl}/study-area/quizzes/generate-with-kana`, {
//                     method: 'POST',
//                     headers: {
//                         'Content-Type': 'application/json',
//                     },
//                     body: JSON.stringify({
//                         assignment_id: assignmentId,
//                         student_id: studentId,
//                         feedback,
//                         weakness_areas: weaknessAreas,
//                         subject,
//                         grade
//                     })
//                 });
//             }

//             if (!response.ok) {
//                 throw new Error(`Backend responded with ${response.status}: ${response.statusText}`);
//             }

//             const quiz = await response.json();
//             console.log('✅ Quiz generated successfully via backend:', quiz.id);

//             // Save to local storage as backup
//             try {
//                 const existingQuizzes = this.getStoredQuizzes();
//                 existingQuizzes[quiz.id] = quiz;
//                 localStorage.setItem(this.storageKey, JSON.stringify(existingQuizzes));
//                 console.log('✅ Quiz saved to local storage');
//             } catch (storageError) {
//                 console.warn('⚠️ Failed to save to local storage:', storageError);
//             }

//             return quiz;

//         } catch (error) {
//             console.error('❌ Failed to generate quiz via backend:', error);

//             // Fallback: generate locally
//             console.log('🔄 Using local fallback generation...');
//             return this.generateFallbackQuiz(assignmentId, studentId, feedback, weaknessAreas, subject, grade);
//         }
//     }

//     /**
//      * Generate a fallback quiz when backend is unavailable
//      */
//     private generateFallbackQuiz(
//         assignmentId: number,
//         studentId: number,
//         _feedback: string,
//         weaknessAreas: string[],
//         subject: string,
//         grade: number
//     ): GeneratedQuiz {
//         console.log('⚠️ Generating fallback quiz locally');

//         // Determine difficulty based on grade
//         const difficulty = this.determineDifficulty(grade);

//         // Generate fallback questions
//         const questions = this.generateFallbackQuestions(weaknessAreas, subject, difficulty);

//         // Create quiz object
//         const quiz: GeneratedQuiz = {
//             id: `quiz_${assignmentId}_${studentId}_${Date.now()}`,
//             assignment_id: assignmentId,
//             student_id: studentId,
//             title: `Improvement Quiz - Assignment Review`,
//             description: `This quiz is designed to help you improve in areas where you can grow. Focus on the concepts and take your time!`,
//             questions: questions.slice(0, 5), // Limit to 5 questions
//             weakness_areas: weaknessAreas,
//             created_at: new Date().toISOString(),
//             attempts: [],
//             max_attempts: 3,
//             time_limit_minutes: 15
//         };

//         // Save quiz to local storage
//         try {
//             const existingQuizzes = this.getStoredQuizzes();
//             existingQuizzes[quiz.id] = quiz;
//             localStorage.setItem(this.storageKey, JSON.stringify(existingQuizzes));
//             console.log('✅ Fallback quiz saved to local storage');
//         } catch (error) {
//             console.warn('⚠️ Failed to save fallback quiz to local storage:', error);
//         }

//         return quiz;
//     }

//     /**
//      * Generate fallback questions when Kana AI is unavailable
//      */
//     private generateFallbackQuestions(weaknessAreas: string[], subject: string, difficulty: string): QuizQuestion[] {
//         const questions: QuizQuestion[] = [];

//         const templates = [
//             {
//                 question: `Which strategy would be most effective for improving your understanding of ${weaknessAreas[0] || 'this topic'}?`,
//                 options: [
//                     `Practice fundamental concepts in ${weaknessAreas[0] || 'the subject'}`,
//                     "Focus only on advanced problems",
//                     "Skip the basics and move to complex topics",
//                     "Memorize answers without understanding"
//                 ],
//                 correctAnswer: 0,
//                 explanation: `Building a strong foundation in ${weaknessAreas[0] || 'fundamental concepts'} is essential for long-term understanding and success.`,
//                 topic: subject,
//                 weakness_area: weaknessAreas[0] || "General Understanding"
//             },
//             {
//                 question: `What is the most important step when encountering difficulties in ${subject}?`,
//                 options: [
//                     "Identify specific knowledge gaps",
//                     "Give up immediately",
//                     "Only focus on easy problems",
//                     "Avoid asking for help"
//                 ],
//                 correctAnswer: 0,
//                 explanation: "Identifying specific knowledge gaps helps you focus your study efforts on areas that need the most improvement.",
//                 topic: subject,
//                 weakness_area: weaknessAreas[1] || "Problem Solving"
//             },
//             {
//                 question: `How can you best apply feedback to improve your performance in ${subject}?`,
//                 options: [
//                     "Ignore the feedback completely",
//                     "Read it once and forget about it",
//                     "Use it to guide focused practice and study",
//                     "Only focus on positive comments"
//                 ],
//                 correctAnswer: 2,
//                 explanation: "Using feedback to guide focused practice helps you address specific weaknesses and improve systematically.",
//                 topic: subject,
//                 weakness_area: weaknessAreas[2] || "Learning Strategies"
//             },
//             {
//                 question: `What approach works best for mastering challenging concepts in ${subject}?`,
//                 options: [
//                     "Rush through practice problems",
//                     "Break complex problems into smaller parts",
//                     "Avoid practicing difficult topics",
//                     "Study only the night before tests"
//                 ],
//                 correctAnswer: 1,
//                 explanation: "Breaking complex problems into smaller, manageable parts makes them easier to understand and solve.",
//                 topic: subject,
//                 weakness_area: weaknessAreas[3] || "Critical Thinking"
//             },
//             {
//                 question: `Which habit will most help you succeed in ${subject}?`,
//                 options: [
//                     "Cramming before exams",
//                     "Regular practice and review",
//                     "Avoiding challenging problems",
//                     "Working alone without seeking help"
//                 ],
//                 correctAnswer: 1,
//                 explanation: "Regular practice and review helps build understanding gradually and reinforces learning over time.",
//                 topic: subject,
//                 weakness_area: weaknessAreas[4] || "Study Habits"
//             }
//         ];

//         for (let i = 0; i < Math.min(5, templates.length); i++) {
//             const template = templates[i];
//             questions.push({
//                 id: `fallback_q_${Date.now()}_${i}`,
//                 question: template.question,
//                 options: template.options,
//                 correctAnswer: template.correctAnswer,
//                 explanation: template.explanation,
//                 difficulty: difficulty as 'easy' | 'medium' | 'hard',
//                 topic: template.topic,
//                 weakness_area: template.weakness_area
//             });
//         }

//         return questions;
//     }

//     /**
//      * Determine quiz difficulty based on assignment grade
//      */
//     private determineDifficulty(grade: number): 'easy' | 'medium' | 'hard' {
//         if (grade < 60) return 'easy';
//         if (grade < 80) return 'medium';
//         return 'hard';
//     }


//     /**
//      * Save quiz to backend or local storage
//      */
//     private async saveQuiz(quiz: GeneratedQuiz): Promise<void> {
//         try {
//             // Try to save to backend first
//             const token = localStorage.getItem('access_token');
//             if (token) {
//                 const response = await fetch(`${this.baseUrl}/study-area/quizzes/generated`, {
//                     method: 'POST',
//                     headers: {
//                         'Authorization': `Bearer ${token}`,
//                         'Content-Type': 'application/json'
//                     },
//                     body: JSON.stringify(quiz)
//                 });

//                 if (response.ok) {
//                     console.log('✅ Quiz saved to backend');
//                     return;
//                 }
//             }

//             // Fallback to local storage
//             const storageKey = `generated_quizzes_${quiz.student_id}`;
//             const existingQuizzes = JSON.parse(localStorage.getItem(storageKey) || '[]');
//             existingQuizzes.push(quiz);
//             localStorage.setItem(storageKey, JSON.stringify(existingQuizzes));

//             console.log('✅ Quiz saved to local storage');
//         } catch (error) {
//             console.error('❌ Failed to save quiz:', error);
//         }
//     }

//     /**
//      * Get quiz by ID
//      */
//     public async getQuiz(quizId: string, studentId: number): Promise<GeneratedQuiz | null> {
//         try {
//             // Try backend first
//             const token = localStorage.getItem('access_token');
//             if (token) {
//                 const response = await fetch(`${this.baseUrl}/study-area/quizzes/generated/${quizId}`, {
//                     headers: {
//                         'Authorization': `Bearer ${token}`,
//                         'Content-Type': 'application/json'
//                     }
//                 });

//                 if (response.ok) {
//                     const quiz = await response.json();
//                     return quiz;
//                 }
//             }

//             // Fallback to local storage
//             const storageKey = `generated_quizzes_${studentId}`;
//             const quizzes = JSON.parse(localStorage.getItem(storageKey) || '[]');
//             return quizzes.find((q: GeneratedQuiz) => q.id === quizId) || null;

//         } catch (error) {
//             console.error('❌ Failed to get quiz:', error);
//             return null;
//         }
//     }

//     /**
//      * Submit quiz attempt
//      */
//     public async submitQuizAttempt(
//         quizId: string,
//         studentId: number,
//         answers: { [questionId: string]: number },
//         timeTakenSeconds: number
//     ): Promise<QuizAttempt | null> {
//         try {
//             const quiz = await this.getQuiz(quizId, studentId);
//             if (!quiz) {
//                 throw new Error('Quiz not found');
//             }

//             // Calculate score
//             let correctAnswers = 0;
//             quiz.questions.forEach(question => {
//                 if (answers[question.id] === question.correctAnswer) {
//                     correctAnswers++;
//                 }
//             });

//             const score = Math.round((correctAnswers / quiz.questions.length) * 100);

//             // Generate feedback
//             const feedback = this.generateAttemptFeedback(quiz, answers, score);

//             const attempt: QuizAttempt = {
//                 id: `attempt_${Date.now()}`,
//                 quiz_id: quizId,
//                 student_id: studentId,
//                 answers,
//                 score,
//                 completed_at: new Date().toISOString(),
//                 time_taken_seconds: timeTakenSeconds,
//                 feedback
//             };

//             // Add attempt to quiz
//             quiz.attempts.push(attempt);

//             // Save updated quiz
//             await this.saveQuiz(quiz);

//             console.log('✅ Quiz attempt submitted:', attempt.id);
//             return attempt;

//         } catch (error) {
//             console.error('❌ Failed to submit quiz attempt:', error);
//             return null;
//         }
//     }

//     /**
//      * Generate feedback for quiz attempt
//      */
//     private generateAttemptFeedback(
//         quiz: GeneratedQuiz,
//         answers: { [questionId: string]: number },
//         score: number
//     ): string {
//         let feedback = '';

//         if (score >= 80) {
//             feedback = `Excellent work! You scored ${score}% and show great improvement in your understanding. `;
//         } else if (score >= 60) {
//             feedback = `Good effort! You scored ${score}% and are making progress. `;
//         } else {
//             feedback = `You scored ${score}%. Don't worry, this is a learning opportunity! `;
//         }

//         const incorrectAreas: string[] = [];
//         quiz.questions.forEach(question => {
//             if (answers[question.id] !== question.correctAnswer) {
//                 incorrectAreas.push(question.weakness_area);
//             }
//         });

//         if (incorrectAreas.length > 0) {
//             feedback += `Consider reviewing: ${incorrectAreas.join(', ')}. `;
//         }

//         feedback += `Remember, this quiz is designed to help you learn and doesn't affect your assignment grade.`;

//         return feedback;
//     }

//     /**
//      * Get student's quizzes for a specific assignment
//      */
//     public async getStudentQuizzesForAssignment(
//         studentId: number,
//         assignmentId: number
//     ): Promise<GeneratedQuiz[]> {
//         try {
//             // Try backend first
//             const token = localStorage.getItem('access_token');
//             if (token) {
//                 const response = await fetch(
//                     `${this.baseUrl}/study-area/quizzes/generated/student/${studentId}/assignment/${assignmentId}`,
//                     {
//                         headers: {
//                             'Authorization': `Bearer ${token}`,
//                             'Content-Type': 'application/json'
//                         }
//                     }
//                 );

//                 if (response.ok) {
//                     return await response.json();
//                 }
//             }

//             // Fallback to local storage
//             const storageKey = `generated_quizzes_${studentId}`;
//             const quizzes = JSON.parse(localStorage.getItem(storageKey) || '[]');
//             return quizzes.filter((q: GeneratedQuiz) => q.assignment_id === assignmentId);

//         } catch (error) {
//             console.error('❌ Failed to get student quizzes:', error);
//             return [];
//         }
//     }

//     /**
//      * Check if student can take quiz (based on max attempts)
//      */
//     public canTakeQuiz(quiz: GeneratedQuiz): boolean {
//         if (!quiz || !quiz.attempts) {
//             return true; // If no attempts array exists, allow taking the quiz
//         }
//         return quiz.attempts.length < quiz.max_attempts;
//     }

//     /**
//      * Get best attempt for a quiz
//      */
//     public getBestAttempt(quiz: GeneratedQuiz): QuizAttempt | null {
//         if (!quiz || !quiz.attempts || quiz.attempts.length === 0) {
//             return null;
//         }

//         return quiz.attempts.reduce((best, current) =>
//             current.score > best.score ? current : best
//         );
//     }
// }

// export const quizGeneratorService = new QuizGeneratorServiceClass();
