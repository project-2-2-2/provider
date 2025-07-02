import requests
import time
import pandas as pd
from collections import Counter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

def get_codeforces_user_data(handle: str):
    base_url = "https://codeforces.com/api/"
    user_info_url = f"{base_url}user.info?handles={handle}"
    user_status_url = f"{base_url}user.status?handle={handle}"

    user_rating = None
    submissions_data = []

    try:
        user_info_response = requests.get(user_info_url)
        user_info_response.raise_for_status()
        user_info_data = user_info_response.json()

        if user_info_data['status'] == 'OK' and user_info_data['result']:
            user_rating = user_info_data['result'][0].get('rating')

        time.sleep(0.5)

        user_status_response = requests.get(user_status_url)
        user_status_response.raise_for_status()
        user_status_data = user_status_response.json()

        if user_status_data['status'] == 'OK' and user_status_data['result']:
            for submission in user_status_data['result']:
                problem = submission.get('problem', {})
                contest_id = problem.get('contestId')
                problem_index = problem.get('index')
                if contest_id is not None and problem_index is not None:
                    problem_id_str = f"{contest_id}-{problem_index}"
                else:
                    continue
                submissions_data.append({
                    'problem_id': problem_id_str,
                    'problem_name': problem.get('name'),
                    'problem_rating': problem.get('rating'),
                    'problem_tags': problem.get('tags', []),
                    'verdict': submission.get('verdict')
                })

    except requests.exceptions.RequestException as e:
        pass
    except ValueError as e:
        pass

    return {
        'rating': user_rating,
        'submissions': submissions_data
    }

def get_all_codeforces_problems_from_api():
    url = "https://codeforces.com/api/problemset.problems"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data['status'] == 'OK':
            problems = []
            for p in data['result']['problems']:
                contest_id = p.get('contestId')
                problem_index = p.get('index')
                if contest_id is not None and problem_index is not None:
                    problem_id_str = f"{contest_id}-{problem_index}"
                else:
                    continue

                rating = p.get('rating')
                if rating is not None:
                    try:
                        rating = int(rating)
                    except (ValueError, TypeError):
                        rating = None
                
                tags = p.get('tags', [])
                if not isinstance(tags, list):
                    tags = []
                tags = [str(tag) for tag in tags]

                problems.append({
                    'problem_id': problem_id_str,
                    'problem_name': p.get('name'),
                    'problem_rating': rating,
                    'problem_tags': tags
                })
            return pd.DataFrame(problems)
        else:
            return pd.DataFrame()
    except requests.exceptions.RequestException as e:
        return pd.DataFrame()
    except ValueError as e:
        return pd.DataFrame()

def analyze_user_data(user_data: dict):
    submissions_df = pd.DataFrame(user_data['submissions'])

    if submissions_df.empty:
        return {
            'solved_problems': set(),
            'unsolved_attempts': set(),
            'solved_problem_ratings': [],
            'attempted_problem_ratings': [],
            'tag_success_rates': {},
            'preferred_tags': Counter(),
            'struggled_tags': Counter()
        }

    problem_verdicts = {}
    for _, row in submissions_df.iterrows():
        prob_id = row['problem_id']
        verdict = row['verdict']
        if prob_id not in problem_verdicts:
            problem_verdicts[prob_id] = {'verdict': verdict, 'row': row}
        elif verdict == 'OK':
            problem_verdicts[prob_id] = {'verdict': verdict, 'row': row}

    processed_submissions_df = pd.DataFrame([v['row'] for v in problem_verdicts.values()])

    solved_problems_df = processed_submissions_df[processed_submissions_df['verdict'] == 'OK']
    unsolved_attempts_df = processed_submissions_df[processed_submissions_df['verdict'] != 'OK']

    solved_problems = set(solved_problems_df['problem_id'].tolist())
    unsolved_attempts = set(unsolved_attempts_df['problem_id'].tolist()) - solved_problems

    solved_problem_ratings = solved_problems_df['problem_rating'].dropna().tolist()
    attempted_problem_ratings = processed_submissions_df['problem_rating'].dropna().tolist()

    tag_attempts = Counter()
    tag_solves = Counter()

    for _, row in processed_submissions_df.iterrows():
        verdict = row['verdict']
        for tag in row['problem_tags']:
            tag_attempts[tag] += 1
            if verdict == 'OK':
                tag_solves[tag] += 1

    tag_success_rates = {}
    preferred_tags = Counter()
    struggled_tags = Counter()

    for tag, attempts in tag_attempts.items():
        solves = tag_solves.get(tag, 0)
        if attempts > 0:
            rate = solves / attempts
            tag_success_rates[tag] = rate
            if rate >= 0.75 and attempts >= 5:
                preferred_tags[tag] += 1
            elif rate <= 0.3 and attempts >= 5:
                struggled_tags[tag] += 1

    return {
        'solved_problems': solved_problems,
        'unsolved_attempts': unsolved_attempts,
        'solved_problem_ratings': solved_problem_ratings,
        'attempted_problem_ratings': attempted_problem_ratings,
        'tag_success_rates': tag_success_rates,
        'preferred_tags': preferred_tags,
        'struggled_tags': struggled_tags
    }


def recommend_problems(
    user_rating: int,
    user_analysis: dict,
    all_problems_df: pd.DataFrame,
    num_recommendations: int = 10,
    goal_tags: list = None
):
    if all_problems_df.empty:
        return []

    available_problems_df = all_problems_df[
        ~all_problems_df['problem_id'].isin(user_analysis['solved_problems'])
    ].copy()

    if available_problems_df.empty:
        return []

    if user_rating is None:
        min_rating = 800
        max_rating = 1200
    else:
        min_rating = max(800, user_rating - 250)
        max_rating = user_rating + 200

    difficulty_filtered_problems = available_problems_df[
        (available_problems_df['problem_rating'].isnull()) |
        (available_problems_df['problem_rating'] >= min_rating) &
        (available_problems_df['problem_rating'] <= max_rating)
    ].copy()

    if difficulty_filtered_problems.empty:
        difficulty_filtered_problems = available_problems_df[
            (available_problems_df['problem_rating'].isnull()) |
            (
                (available_problems_df['problem_rating'] >= max(800, (user_rating or 800) - 500)) &
                (available_problems_df['problem_rating'] <= ((user_rating or 1200) + 500))
            )
        ].copy()
        if difficulty_filtered_problems.empty:
            return available_problems_df.sample(min(num_recommendations, len(available_problems_df))).to_dict(orient='records')

    difficulty_filtered_problems['tags_str'] = difficulty_filtered_problems['problem_tags'].apply(
        lambda x: ' '.join(x) if isinstance(x, list) else ''
    )

    user_profile_tags_str = []

    if goal_tags:
        user_profile_tags_str.extend(goal_tags * 5)
    elif user_analysis['struggled_tags']:
        for tag, count in user_analysis['struggled_tags'].items():
            user_profile_tags_str.extend([tag] * (count + 5)) # Increased weight for struggled tags
    elif user_analysis['preferred_tags']:
        for tag, count in user_analysis['preferred_tags'].items():
            user_profile_tags_str.extend([tag] * (count + 1))
    else:
        common_tags = ['dp', 'greedy', 'implementation', 'math', 'data structures', 'algorithms']
        user_profile_tags_str.extend(common_tags * 2)

    if not user_profile_tags_str:
        return difficulty_filtered_problems.sample(min(num_recommendations, len(difficulty_filtered_problems))).to_dict(orient='records')

    user_profile_text = ' '.join(user_profile_tags_str)
    all_text_for_tfidf = difficulty_filtered_problems['tags_str'].tolist() + [user_profile_text]

    vectorizer = TfidfVectorizer()
    try:
        tfidf_matrix = vectorizer.fit_transform(all_text_for_tfidf)
    except ValueError as e:
        if 'similarity' in difficulty_filtered_problems.columns:
            difficulty_filtered_problems = difficulty_filtered_problems.drop(columns=['similarity'])
        return difficulty_filtered_problems.sample(min(num_recommendations, len(difficulty_filtered_problems))).to_dict(orient='records')

    user_profile_vector = tfidf_matrix[-1:]
    problem_vectors = tfidf_matrix[:-1]

    recommended_problems = []

    if problem_vectors.shape[0] > 0 and user_profile_vector.shape[0] > 0:
        cosine_similarities = cosine_similarity(user_profile_vector, problem_vectors).flatten()
        cosine_similarities = np.nan_to_num(cosine_similarities, nan=0.0)

        difficulty_filtered_problems['similarity'] = cosine_similarities

        sorted_problems = difficulty_filtered_problems.sort_values(
            by=['similarity', 'problem_rating'], ascending=[False, True]
        ).reset_index(drop=True)

        final_recommendations_df = sorted_problems[
            ~sorted_problems['problem_id'].isin(user_analysis['unsolved_attempts'])
        ]

        recommended_problems = final_recommendations_df.head(num_recommendations).to_dict(orient='records')
    else:
        recommended_problems = difficulty_filtered_problems.sample(min(num_recommendations, len(difficulty_filtered_problems))).to_dict(orient='records')

    for problem in recommended_problems:
        if pd.isna(problem.get('problem_rating')):
            problem['problem_rating'] = None
        elif isinstance(problem.get('problem_rating'), (np.integer, float)):
            problem['problem_rating'] = int(problem['problem_rating'])

        if '-' in problem['problem_id']:
            contest_id, problem_index = problem['problem_id'].split('-')
            problem['url'] = f"https://codeforces.com/problemset/problem/{contest_id}/{problem_index}"
        else:
            problem['url'] = "#"

    return recommended_problems