import { useState } from "react";
import axios from "axios";


function App() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);


  const startInterview = async () => {
    setLoading(true);

    try {
      const response = await axios.post(
        "http://localhost:8000/api/interview/question",
        {
          resume:
            "I built a React application using Firebase authentication and Firestore.",
          role: "Software Engineer",
          interview_type: "Technical",
          previous_questions: [],
          previous_answers: [],
        }
      );

      setQuestion(response.data.question);

    } catch (error) {
      console.error(error);
      setQuestion(
        "Could not connect to the PrepMate backend."
      );

    } finally {
      setLoading(false);
    }
  };


  return (
    <main className="min-h-screen bg-zinc-950 text-white flex items-center justify-center p-6">

      <div className="w-full max-w-3xl">

        <p className="text-sm text-zinc-500 tracking-widest">
          PRIVATE AI INTERVIEW PARTNER
        </p>

        <h1 className="text-6xl font-bold mt-3">
          PrepMate
        </h1>

        <p className="text-zinc-400 text-lg mt-4">
          Practice interviews with your own local AI interviewer.
        </p>


        <div className="mt-10 bg-zinc-900 border border-zinc-800 rounded-2xl p-8">

          <div className="flex items-center gap-2 text-sm text-zinc-400">

            <div className="w-2 h-2 bg-green-500 rounded-full" />

            Gemma 3 4B · Local

          </div>


          <h2 className="text-2xl font-semibold mt-6">
            Ready for your interview?
          </h2>


          <button
            onClick={startInterview}
            disabled={loading}
            className="mt-8 bg-white text-black px-6 py-3 rounded-xl font-semibold hover:bg-zinc-200 disabled:opacity-50"
          >
            {loading
              ? "Gemma is thinking..."
              : "Start Interview"}
          </button>


          {question && (
            <div className="mt-10 border-t border-zinc-800 pt-8">

              <p className="text-xs text-zinc-500 tracking-widest">
                QUESTION 01
              </p>

              <p className="text-xl leading-relaxed mt-4">
                {question}
              </p>

            </div>
          )}

        </div>

      </div>

    </main>
  );
}


export default App;