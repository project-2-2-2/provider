# backend/main.py
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import core_recommender
import database
import pandas as pd
from dotenv import load_dotenv
import os
import threading
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

app = FastAPI(
    title="Codeforces Problem Recommender API",
    description="An AI-powered API to recommend Codeforces problems based on user data.",
    version="0.1.0",
)
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",  
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

all_codeforces_problems_df: pd.DataFrame = pd.DataFrame()
last_problem_fetch_time = 0

def update_problems_background_task():
    global all_codeforces_problems_df, last_problem_fetch_time
    UPDATE_INTERVAL_SECONDS = 6 * 3600
    while True:
        current_time = time.time()
        if current_time - last_problem_fetch_time > UPDATE_INTERVAL_SECONDS:
            logger.info("Starting periodic update of all Codeforces problems...")
            fetched_problems = core_recommender.get_all_codeforces_problems_from_api()
            if not fetched_problems.empty:
                all_codeforces_problems_df = fetched_problems
                database.save_problems_to_db(all_codeforces_problems_df)
                logger.info(f"Successfully updated {len(all_codeforces_problems_df)} problems and saved to DB.")
                last_problem_fetch_time = current_time
            else:
                logger.warning("Failed to fetch all problems during background update. Retrying later.")
        time.sleep(UPDATE_INTERVAL_SECONDS / 2)

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup initiated.")
    database.create_db_and_tables()

    global all_codeforces_problems_df, last_problem_fetch_time

    problems_from_db = database.get_problems_from_db()
    if not problems_from_db.empty:
        all_codeforces_problems_df = problems_from_db
        last_problem_fetch_time = time.time()
        logger.info(f"Loaded {len(all_codeforces_problems_df)} problems from database on startup.")
    else:
        logger.info("No problems in database. Performing initial fetch from Codeforces API...")
        # THIS IS THE LINE THAT NEEDS TO BE CHANGED
        all_codeforces_problems_df = core_recommender.get_all_codeforces_problems_from_api() # <-- FIX IS HERE
        if not all_codeforces_problems_df.empty:
            database.save_problems_to_db(all_codeforces_problems_df)
            last_problem_fetch_time = time.time()
            logger.info(f"Successfully fetched {len(all_codeforces_problems_df)} problems from API and saved to DB.")
        else:
            logger.error("Initial fetch of all problems failed. Recommendations may not be available.")

    threading.Thread(target=update_problems_background_task, daemon=True).start()
    logger.info("Background problem update task started.")


@app.get("/")
async def read_root():
    return {"message": "Codeforces Problem Recommender API is running! Visit /docs for API documentation."}

@app.get("/recommend/{handle}")
async def get_recommendations(
    handle: str,
    num_recommendations: int = 10,
    goal_tags: str = None
):
    if all_codeforces_problems_df.empty:
        logger.error("Attempted recommendation with empty problem database.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Problem database not initialized. Please try again in a moment."
        )

    logger.info(f"Received request for handle: {handle}, num_recommendations: {num_recommendations}, goal_tags: {goal_tags}")

    parsed_goal_tags = [tag.strip().lower() for tag in goal_tags.split(',')] if goal_tags else None

    user_data = core_recommender.get_codeforces_user_data(handle)

    if user_data['rating'] is None and not user_data['submissions']:
        logger.warning(f"No rating or submissions found for handle: {handle}.")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Could not retrieve sufficient data for handle: {handle}. Please check the handle or ensure they have public submissions."
        )

    user_analysis = core_recommender.analyze_user_data(user_data)

    recommendations = core_recommender.recommend_problems(
        user_data['rating'],
        user_analysis,
        all_codeforces_problems_df,
        num_recommendations,
        goal_tags=parsed_goal_tags
    )

    logger.info(f"Generated {len(recommendations)} recommendations for {handle}.")

    return {
        "handle": handle,
        "user_rating": user_data['rating'],
        "solved_count": len(user_analysis['solved_problems']),
        "unsolved_attempts_count": len(user_analysis['unsolved_attempts']),
        "tag_success_rates": user_analysis['tag_success_rates'],
        "preferred_tags": user_analysis['preferred_tags'].most_common(5),
        "struggled_tags": user_analysis['struggled_tags'].most_common(5),
        "recommendations": recommendations
    }