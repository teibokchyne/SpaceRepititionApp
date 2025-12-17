from flask import Flask, request, redirect, jsonify
from database import init_db, get_db_connection
from datetime import datetime
import markdown

app = Flask(__name__)

# Initialize database on app startup
with app.app_context():
    init_db()


def format_date(date_string):
    """Format date string to human-readable format."""
    try:
        if isinstance(date_string, str):
            # Parse ISO format datetime
            dt = datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        else:
            dt = date_string
        # Format as: Monday, December 10, 2025 at 2:30 PM
        return dt.strftime('%A, %B %d, %Y at %I:%M %p')
    except:
        return date_string


@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        text = request.form.get('text')
        if text:
            conn = get_db_connection()
            conn.execute('INSERT INTO notes (text) VALUES (?)', (text,))
            conn.commit()
            conn.close()
        return redirect('/')

    # Pagination settings
    page = request.args.get('page', 1, type=int)
    notes_per_page = 20
    offset = (page - 1) * notes_per_page

    # Date filter settings
    filter_type = request.args.get('filter', 'all', type=str)
    filter_date = request.args.get('date', '', type=str)
    sort_order = request.args.get('sort', 'asc', type=str)
    # Search term for notes (used in template only)
    filter_q = request.args.get('q', '', type=str)

    conn = get_db_connection()
    items = conn.execute('SELECT * FROM items').fetchall()

    # Build query based on filter
    query = 'SELECT * FROM notes'
    query_count = 'SELECT COUNT(*) as count FROM notes'

    if filter_type == 'before' and filter_date:
        query += f' WHERE date < "{filter_date}"'
        query_count += f' WHERE date < "{filter_date}"'
    elif filter_type == 'after' and filter_date:
        query += f' WHERE date > "{filter_date}"'
        query_count += f' WHERE date > "{filter_date}"'
    elif filter_type == 'on' and filter_date:
        query += f' WHERE date LIKE "{filter_date}%"'
        query_count += f' WHERE date LIKE "{filter_date}%"'

    # Get total count of notes with filter
    total_notes = conn.execute(query_count).fetchone()['count']

    # Get paginated notes with sort order
    # Sort by date first, then by stars (ascending) within the same day
    order_direction = 'DESC' if sort_order == 'desc' else 'ASC'
    query += f' ORDER BY DATE(date) {order_direction}, stars ASC LIMIT ? OFFSET ?'
    notes = conn.execute(query, (notes_per_page, offset)).fetchall()
    conn.close()

    # Calculate total pages
    total_pages = (total_notes + notes_per_page - 1) // notes_per_page

    items_html = ''
    if items:
        items_html = '<ul>'
        for item in items:
            items_html += f'<li>{item["name"]}: {item["description"]}</li>'
        items_html += '</ul>'
    else:
        items_html = '<p>No items in the database yet.</p>'

    notes_html = ''
    if notes:
        notes_html = '<table border="1" style="width:100%; border-collapse: collapse;">'
        notes_html += '<tr><th style="padding: 10px;">Text</th><th style="padding: 10px;">Date</th><th style="padding: 10px;">Importance</th><th style="padding: 10px;">Actions</th><th style="padding: 10px;">Change Date</th></tr>'
        for note in notes:
            formatted_date = format_date(note["date"])
            try:
                stars = note["stars"] if note["stars"] else 0
            except (IndexError, KeyError):
                stars = 0
            star_html = '⭐' * stars if stars > 0 else '✩ (0 stars)'

            # Star rating buttons
            star_buttons = '<div style="display: flex; gap: 3px; flex-wrap: wrap;">'
            for star_count in range(1, 6):
                star_buttons += f'<a href="/rate-note/{note["id"]}/{star_count}" style="padding: 3px 8px; background-color: #FFD700; color: black; text-decoration: none; border-radius: 3px; font-size: 12px; cursor: pointer;">{"⭐" * star_count}</a>'
            star_buttons += '</div>'

            date_buttons = '<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
            for days in [1, 3, 7, 14, 30]:
                date_buttons += f'<a href="/increment-date/{note["id"]}/{days}" style="padding: 3px 8px; background-color: #FF9800; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">+{days}d</a>'
            date_buttons += '</div>'
            notes_html += f'<tr><td style="padding: 10px;">{note["text"]}</td><td style="padding: 10px;">{formatted_date}</td><td style="padding: 10px;">{star_html}</td><td style="padding: 10px;"><a href="/delete/{note["id"]}" style="margin-right: 10px; padding: 5px 10px; background-color: #f44336; color: white; text-decoration: none; border-radius: 4px;">Delete</a><a href="/edit/{note["id"]}" style="padding: 5px 10px; background-color: #2196F3; color: white; text-decoration: none; border-radius: 4px;">Edit</a></td><td style="padding: 10px;">{date_buttons}</td></tr>'
            notes_html += f'<tr><td colspan="5" style="padding: 5px 10px; background-color: #fafafa;"><strong>Rate:</strong> {star_buttons}</td></tr>'
        notes_html += '</table>'

        # Add pagination controls
        notes_html += '<div style="margin-top: 20px; text-align: center;">'
        notes_html += f'<p>Page {page} of {total_pages} (Total: {total_notes} notes)</p>'
        notes_html += '<div>'

        if page > 1:
            notes_html += f'<a href="/?page=1" style="margin: 0 5px;">First</a>'
            notes_html += f'<a href="/?page={page-1}" style="margin: 0 5px;">Previous</a>'

        notes_html += f'<span style="margin: 0 10px;">Page {page}</span>'

        if page < total_pages:
            notes_html += f'<a href="/?page={page+1}" style="margin: 0 5px;">Next</a>'
            notes_html += f'<a href="/?page={total_pages}" style="margin: 0 5px;">Last</a>'

        notes_html += '</div></div>'
    else:
        notes_html = '<p>No notes yet.</p>'

    navbar = '''
        <nav style="background-color: #333; padding: 0; margin: 0; position: sticky; top: 0; z-index: 1000;">
            <ul style="list-style: none; margin: 0; padding: 0; display: flex;">
                <li style="margin: 0;"><a href="/" style="display: block; padding: 15px 20px; color: white; text-decoration: none; background-color: #333; transition: background-color 0.3s;">Home</a></li>
                <li style="margin: 0;"><a href="/practice" style="display: block; padding: 15px 20px; color: white; text-decoration: none; background-color: #333; transition: background-color 0.3s;">Spaced Repetition</a></li>
            </ul>
        </nav>
    '''

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Home</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
            }}
            nav ul li a:hover {{
                background-color: #555 !important;
            }}
            textarea {{
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                font-size: 14px;
            }}
            button {{
                padding: 10px 20px;
                font-size: 16px;
                cursor: pointer;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
            }}
            button:hover {{
                background-color: #45a049;
            }}
            h2 {{
                color: #333;
                border-bottom: 2px solid #4CAF50;
                padding-bottom: 10px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            table th, table td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            table th {{
                background-color: #4CAF50;
                color: white;
            }}
            table tr:nth-child(even) {{
                background-color: #f2f2f2;
            }}
        </style>
    </head>
    <body>
        {navbar}
        <h1>Welcome to the Home Page</h1>
        <p>This is a simple Flask application with SQLite database.</p>
        
        <h2>Add a Note</h2>
        <form method="post">
            <textarea name="text" placeholder="Enter your note here..." required></textarea>
            <button type="submit">Save Note</button>
        </form>
        
        <h2>Filter Notes by Date</h2>
        <form method="get" style="margin-bottom: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 4px;">
            <label for="filter" style="margin-right: 10px; font-weight: bold;">Filter Type:</label>
            <select name="filter" id="filter" style="padding: 8px; margin-right: 20px;">
                <option value="all" {"selected" if filter_type == "all" else ""}>All Notes</option>
                <option value="before" {"selected" if filter_type == "before" else ""}>Before Date</option>
                <option value="after" {"selected" if filter_type == "after" else ""}>After Date</option>
                <option value="on" {"selected" if filter_type == "on" else ""}>On Date</option>
            </select>
            <label for="date" style="margin-right: 10px; font-weight: bold;">Date:</label>
            <input type="date" name="date" id="date" value="{filter_date}" style="padding: 8px; margin-right: 20px;">
            <label for="sort" style="margin-right: 10px; font-weight: bold;">Sort Order:</label>
            <select name="sort" id="sort" style="padding: 8px; margin-right: 20px;">
                <option value="asc" {"selected" if sort_order == "asc" else ""}>Oldest First (Ascending)</option>
                <option value="desc" {"selected" if sort_order == "desc" else ""}>Newest First (Descending)</option>
            </select>
            <label for="q" style="margin-right: 10px; font-weight: bold;">Search:</label>
            <input type="text" name="q" id="q" value="{filter_q}" placeholder="Search question or answer" style="padding: 8px; margin-right: 20px;">
            <button type="submit" style="padding: 8px 16px; background-color: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer;">Filter</button>
            <a href="/" style="padding: 8px 16px; background-color: #999; color: white; text-decoration: none; border-radius: 4px; display: inline-block; margin-left: 10px;">Clear Filter</a>
        </form>
        
        <h2>Notes:</h2>
        {notes_html}
    </body>
    </html>
    '''


@app.route('/delete/<int:note_id>', methods=['GET'])
def delete_note(note_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM notes WHERE id = ?', (note_id,))
    conn.commit()
    conn.close()
    return redirect('/')


@app.route('/edit/<int:note_id>', methods=['GET', 'POST'])
def edit_note(note_id):
    if request.method == 'POST':
        text = request.form.get('text')
        if text:
            conn = get_db_connection()
            conn.execute('UPDATE notes SET text = ? WHERE id = ?',
                         (text, note_id))
            conn.commit()
            conn.close()
        return redirect('/')

    conn = get_db_connection()
    note = conn.execute('SELECT * FROM notes WHERE id = ?',
                        (note_id,)).fetchone()
    conn.close()

    if note is None:
        return redirect('/')

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Edit Note</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
            }}
            textarea {{
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                font-size: 14px;
            }}
            button {{
                padding: 10px 20px;
                font-size: 16px;
                cursor: pointer;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                margin-right: 10px;
            }}
            button:hover {{
                background-color: #45a049;
            }}
            a {{
                padding: 10px 20px;
                font-size: 16px;
                background-color: #999;
                color: white;
                text-decoration: none;
                border-radius: 4px;
            }}
            a:hover {{
                background-color: #777;
            }}
            h1 {{
                color: #333;
            }}
        </style>
    </head>
    <body>
        <h1>Edit Note</h1>
        <form method="post">
            <textarea name="text" required>{note["text"]}</textarea>
            <button type="submit">Update Note</button>
            <a href="/">Cancel</a>
        </form>
    </body>
    </html>
    '''


@app.route('/increment-date/<int:note_id>/<int:days>', methods=['GET'])
def increment_date(note_id, days):
    from datetime import datetime, timedelta

    conn = get_db_connection()
    note = conn.execute('SELECT * FROM notes WHERE id = ?',
                        (note_id,)).fetchone()

    if note:
        current_date = datetime.fromisoformat(
            note['date'].replace('Z', '+00:00'))
        new_date = current_date + timedelta(days=days)
        conn.execute('UPDATE notes SET date = ? WHERE id = ?',
                     (new_date.isoformat(), note_id))
        conn.commit()

    conn.close()
    return redirect('/')


@app.route('/rate-note/<int:note_id>/<int:stars>', methods=['GET'])
def rate_note(note_id, stars):
    """Rate a note with 1-5 stars."""
    if 1 <= stars <= 5:
        conn = get_db_connection()
        conn.execute('UPDATE notes SET stars = ? WHERE id = ?',
                     (stars, note_id))
        conn.commit()
        conn.close()

    return redirect('/')


@app.route('/increment-practice-date/<int:practice_id>/<int:days>', methods=['GET'])
def increment_practice_date(practice_id, days):
    """Increment the date of a spaced repetition practice item."""
    from datetime import timedelta

    conn = get_db_connection()
    practice = conn.execute('SELECT * FROM spaced_repetition WHERE id = ?',
                            (practice_id,)).fetchone()

    if practice:
        current_date = datetime.fromisoformat(
            practice['date'].replace('Z', '+00:00'))
        new_date = current_date + timedelta(days=days)
        conn.execute('UPDATE spaced_repetition SET date = ? WHERE id = ?',
                     (new_date.isoformat(), practice_id))
        conn.commit()

    conn.close()
    return redirect('/practice')


@app.route('/rate-practice/<int:practice_id>/<int:stars>', methods=['GET'])
def rate_practice(practice_id, stars):
    """Rate a practice item with 1-5 stars."""
    if 1 <= stars <= 5:
        conn = get_db_connection()
        conn.execute('UPDATE spaced_repetition SET stars = ? WHERE id = ?',
                     (stars, practice_id))
        conn.commit()
        conn.close()

    return redirect('/practice')


@app.route('/edit-practice/<int:practice_id>', methods=['GET', 'POST'])
def edit_practice(practice_id):
    """Edit a practice item."""
    if request.method == 'POST':
        subject = request.form.get('subject')
        topic = request.form.get('topic')
        question = request.form.get('question')
        answer = request.form.get('answer')
        if subject and topic and question and answer:
            conn = get_db_connection()
            conn.execute(
                'UPDATE spaced_repetition SET subject = ?, topic = ?, question = ?, answer = ? WHERE id = ?',
                (subject, topic, question, answer, practice_id)
            )
            conn.commit()
            conn.close()
        return redirect('/practice')

    conn = get_db_connection()
    practice = conn.execute('SELECT * FROM spaced_repetition WHERE id = ?',
                            (practice_id,)).fetchone()
    conn.close()

    if practice is None:
        return redirect('/practice')

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Edit Practice Item</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
            }}
            input, textarea {{
                width: 100%;
                padding: 10px;
                margin: 10px 0;
                font-size: 14px;
                box-sizing: border-box;
            }}
            button {{
                padding: 10px 20px;
                font-size: 16px;
                cursor: pointer;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                margin-right: 10px;
            }}
            button:hover {{
                background-color: #45a049;
            }}
            a {{
                padding: 10px 20px;
                font-size: 16px;
                background-color: #999;
                color: white;
                text-decoration: none;
                border-radius: 4px;
            }}
            a:hover {{
                background-color: #777;
            }}
            h1 {{
                color: #333;
            }}
            .form-group {{
                margin-bottom: 15px;
            }}
            .form-group label {{
                display: block;
                font-weight: bold;
                margin-bottom: 5px;
            }}
        </style>
    </head>
    <body>
        <h1>Edit Practice Item</h1>
        <form method="post">
            <div class="form-group">
                <label for="subject">Subject:</label>
                <input type="text" name="subject" id="subject" value="{practice["subject"]}" required>
            </div>
            <div class="form-group">
                <label for="topic">Topic:</label>
                <input type="text" name="topic" id="topic" value="{practice["topic"]}" required>
            </div>
            <div class="form-group">
                <label for="question">Question:</label>
                <textarea name="question" id="question" required>{practice["question"]}</textarea>
            </div>
            <div class="form-group">
                <label for="answer">Answer:</label>
                <textarea name="answer" id="answer" required>{practice["answer"]}</textarea>
            </div>
            <button type="submit">Update Practice Item</button>
            <a href="/practice">Cancel</a>
        </form>
    </body>
    </html>
    '''


@app.route('/delete-practice/<int:practice_id>', methods=['GET'])
def delete_practice(practice_id):
    """Delete a practice item."""
    conn = get_db_connection()
    conn.execute('DELETE FROM spaced_repetition WHERE id = ?', (practice_id,))
    conn.commit()
    conn.close()
    return redirect('/practice')


@app.route('/practice', methods=['GET', 'POST'])
def practice():
    """Display all spaced repetition practice items."""
    if request.method == 'POST':
        subject = request.form.get('subject')
        topic = request.form.get('topic')
        question = request.form.get('question')
        answer = request.form.get('answer')
        if subject and topic and question and answer:
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO spaced_repetition (subject, topic, question, answer) VALUES (?, ?, ?, ?)',
                (subject, topic, question, answer)
            )
            conn.commit()
            conn.close()
        return redirect('/practice')

    # Pagination settings
    page = request.args.get('page', 1, type=int)
    items_per_page = 1
    offset = (page - 1) * items_per_page

    # Filter settings
    filter_subject = request.args.get('subject', '', type=str)
    filter_topic = request.args.get('topic', '', type=str)
    filter_date = request.args.get('date', '', type=str)
    filter_type = request.args.get('filter', 'all', type=str)
    filter_stars = request.args.get('stars', '', type=str)
    # Full-text search over question/answer
    filter_q = request.args.get('q', '', type=str)

    conn = get_db_connection()

    # Build parameterized query based on filters (safer)
    query = 'SELECT * FROM spaced_repetition'
    query_count = 'SELECT COUNT(*) as count FROM spaced_repetition'
    conditions = []
    params = []

    if filter_subject:
        conditions.append('subject = ?')
        params.append(filter_subject)
    if filter_topic:
        conditions.append('topic = ?')
        params.append(filter_topic)
    if filter_stars:
        # store as int if provided
        try:
            params.append(int(filter_stars))
            conditions.append('stars = ?')
        except ValueError:
            pass

    if filter_type == 'before' and filter_date:
        conditions.append('date < ?')
        params.append(filter_date)
    elif filter_type == 'after' and filter_date:
        conditions.append('date > ?')
        params.append(filter_date)
    elif filter_type == 'on' and filter_date:
        conditions.append('date LIKE ?')
        params.append(f'{filter_date}%')

    # Full-text like search on question and answer
    if filter_q:
        conditions.append('(question LIKE ? OR answer LIKE ?)')
        like_q = f'%{filter_q}%'
        params.extend([like_q, like_q])

    if conditions:
        where_clause = ' WHERE ' + ' AND '.join(conditions)
        query += where_clause
        query_count += where_clause

    # Get total count of filtered practices
    total_practices = conn.execute(query_count, params).fetchone()['count']

    # Get all filtered practices
    query += ' ORDER BY date ASC, stars ASC'
    all_practices = conn.execute(query, params).fetchall()

    # Add dummy data if table is empty and no filters/search are applied
    if len(all_practices) == 0 and not filter_subject and not filter_topic and not filter_date and not filter_q:
        dummy_data = [
            ('Mathematics', 'Algebra', 'What is the solution to 2x + 5 = 13?',
             'x = 4', datetime.now().isoformat()),
            ('Science', 'Physics', 'What is Newtons second law of motion?',
             'F = ma (Force equals mass times acceleration)', datetime.now().isoformat()),
            ('History', 'World War II', 'In what year did World War II end?',
             '1945', datetime.now().isoformat()),
            ('Biology', 'Cells', 'What is the powerhouse of the cell?',
             'Mitochondria', datetime.now().isoformat()),
            ('Chemistry', 'Periodic Table', 'What is the chemical symbol for Gold?',
             'Au', datetime.now().isoformat()),
        ]
        for subject, topic, question, answer, date in dummy_data:
            conn.execute(
                'INSERT INTO spaced_repetition (subject, topic, question, answer, date) VALUES (?, ?, ?, ?, ?)',
                (subject, topic, question, answer, date)
            )
        conn.commit()
        # re-run unfiltered query to get all practices (no params)
        all_practices = conn.execute(
            'SELECT * FROM spaced_repetition ORDER BY date ASC, stars ASC').fetchall()
        total_practices = len(all_practices)

    # Get paginated items
    practices = all_practices[offset:offset + items_per_page]

    # Calculate total pages
    total_pages = (total_practices + items_per_page - 1) // items_per_page

    # Get unique subjects and topics for filter dropdowns
    all_subjects = conn.execute(
        'SELECT DISTINCT subject FROM spaced_repetition ORDER BY subject').fetchall()
    all_topics = conn.execute(
        'SELECT DISTINCT topic FROM spaced_repetition ORDER BY topic').fetchall()

    conn.close()

    # Build a preserved query string for pagination links to keep filters/search
    params_parts = []
    if filter_subject:
        params_parts.append(f'subject={filter_subject}')
    if filter_topic:
        params_parts.append(f'topic={filter_topic}')
    if filter_type and filter_type != 'all':
        params_parts.append(f'filter={filter_type}')
    if filter_date:
        params_parts.append(f'date={filter_date}')
    if filter_stars:
        params_parts.append(f'stars={filter_stars}')
    if filter_q:
        params_parts.append(f'q={filter_q}')
    params_query = '&'.join(params_parts)

    navbar = '''
        <nav style="background-color: #333; padding: 0; margin: 0; position: sticky; top: 0; z-index: 1000;">
            <ul style="list-style: none; margin: 0; padding: 0; display: flex;">
                <li style="margin: 0;"><a href="/" style="display: block; padding: 15px 20px; color: white; text-decoration: none; background-color: #333; transition: background-color 0.3s;">Home</a></li>
                <li style="margin: 0;"><a href="/practice" style="display: block; padding: 15px 20px; color: white; text-decoration: none; background-color: #333; transition: background-color 0.3s;">Spaced Repetition</a></li>
            </ul>
        </nav>
    '''

    practices_html = ''
    if practices:
        for practice in practices:
            formatted_date = format_date(practice["date"])
            date_buttons = '<div style="display: flex; gap: 5px; flex-wrap: wrap;">'
            for days in [1, 3, 7, 14, 30]:
                date_buttons += f'<a href="/increment-practice-date/{practice["id"]}/{days}" style="padding: 3px 8px; background-color: #FF9800; color: white; text-decoration: none; border-radius: 3px; font-size: 12px;">+{days}d</a>'
            date_buttons += '</div>'

            # Convert answer to markdown
            answer_html = markdown.markdown(practice["answer"])

            # Star rating display
            try:
                stars = practice["stars"] if practice["stars"] else 0
            except (IndexError, KeyError):
                stars = 0
            star_html = '⭐' * stars if stars > 0 else '✩ (0 stars)'

            # Star rating buttons
            star_buttons = '<div style="display: flex; gap: 3px; flex-wrap: wrap;">'
            for star_count in range(1, 6):
                star_buttons += f'<a href="/rate-practice/{practice["id"]}/{star_count}" style="padding: 3px 8px; background-color: #FFD700; color: black; text-decoration: none; border-radius: 3px; font-size: 12px; cursor: pointer;">{"⭐" * star_count}</a>'
            star_buttons += '</div>'

            practices_html += f'''
            <div style="background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 20px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                    <button class="subject-topic-btn" id="subjectTopicBtn-{practice['id']}" onclick="toggleSubjectTopic('{practice['id']}')">Show Subject & Topic</button>
                    <p><strong>Date:</strong> {formatted_date}</p>
                </div>
                
                <div id="subjectTopic-{practice['id']}" class="subject-topic-hidden" style="margin-bottom: 20px;">
                    <p><strong>Subject:</strong> {practice["subject"]}</p>
                    <p><strong>Topic:</strong> {practice["topic"]}</p>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <p><strong>Question:</strong></p>
                    <p style="background-color: white; padding: 10px; border-radius: 4px; border-left: 4px solid #2196F3; white-space: pre-wrap; word-wrap: break-word;">{practice["question"]}</p>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <p><strong>Answer:</strong></p>
                    <button class="answer-btn" id="answerBtn-{practice['id']}" onclick="toggleAnswer('{practice['id']}')">Show Answer</button>
                    <div id="answer-{practice['id']}" class="answer-hidden" style="background-color: white; padding: 10px; border-radius: 4px; border-left: 4px solid #4CAF50; white-space: pre-wrap; word-wrap: break-word;">{answer_html}</div>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <button class="stars-btn" id="starsBtn-{practice['id']}" onclick="toggleStars('{practice['id']}')">Show Importance</button>
                    <div id="stars-{practice['id']}" class="stars-hidden" style="margin-top: 10px;">
                        <p><strong>Importance:</strong> {star_html}</p>
                        <p><strong>Rate:</strong></p>
                        {star_buttons}
                    </div>
                </div>
                
                <div style="margin-top: 20px;">
                    <p><strong>Change Date:</strong></p>
                    {date_buttons}
                </div>
                
                <div style="margin-top: 20px; display: flex; gap: 10px;">
                    <a href="/edit-practice/{practice['id']}" style="padding: 10px 20px; background-color: #2196F3; color: white; text-decoration: none; border-radius: 4px; cursor: pointer;">Edit</a>
                    <a href="/delete-practice/{practice['id']}" style="padding: 10px 20px; background-color: #f44336; color: white; text-decoration: none; border-radius: 4px; cursor: pointer;" onclick="return confirm('Are you sure you want to delete this practice item?');">Delete</a>
                </div>
            </div>
            '''
    else:
        practices_html = '<p>No practice items yet.</p>'

    return f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Spaced Repetition Practice</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
            }}
            nav ul li a:hover {{
                background-color: #555 !important;
            }}
            h1 {{
                color: #333;
            }}
            h2 {{
                color: #333;
                border-bottom: 2px solid #2196F3;
                padding-bottom: 10px;
            }}
            form input, form textarea {{
                padding: 10px;
                margin: 5px 0;
                font-size: 14px;
                width: 100%;
                box-sizing: border-box;
            }}
            form button {{
                padding: 10px 20px;
                font-size: 16px;
                cursor: pointer;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                margin-top: 10px;
            }}
            form button:hover {{
                background-color: #0b7dda;
            }}
            form {{
                background-color: #f9f9f9;
                padding: 20px;
                border-radius: 4px;
                margin-bottom: 20px;
            }}
            .form-group {{
                margin-bottom: 15px;
            }}
            .form-group label {{
                display: block;
                font-weight: bold;
                margin-bottom: 5px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 20px;
            }}
            table th, table td {{
                border: 1px solid #ddd;
                padding: 12px;
                text-align: left;
            }}
            table th {{
                background-color: #2196F3;
                color: white;
            }}
            table tr:nth-child(even) {{
                background-color: #f2f2f2;
            }}
            #addPracticeBtn {{
                padding: 10px 20px;
                font-size: 16px;
                cursor: pointer;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                margin-top: 10px;
                margin-bottom: 20px;
            }}
            #addPracticeBtn:hover {{
                background-color: #45a049;
            }}
            #practiceForm {{
                display: none;
            }}
            #practiceForm.show {{
                display: block;
            }}
            .answer-hidden {{
                display: none;
            }}
            .answer-btn {{
                padding: 8px 16px;
                font-size: 14px;
                cursor: pointer;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                margin-bottom: 10px;
            }}
            .answer-btn:hover {{
                background-color: #45a049;
            }}
            .subject-topic-hidden {{
                display: none;
            }}
            .subject-topic-btn {{
                padding: 8px 16px;
                font-size: 14px;
                cursor: pointer;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
                margin-bottom: 10px;
            }}
            .subject-topic-btn:hover {{
                background-color: #0b7dda;
            }}
            .stars-hidden {{
                display: none;
            }}
            .stars-btn {{
                padding: 8px 16px;
                font-size: 14px;
                cursor: pointer;
                background-color: #FF9800;
                color: white;
                border: none;
                border-radius: 4px;
                margin-bottom: 10px;
            }}
            .stars-btn:hover {{
                background-color: #e68900;
            }}
        </style>
        <script>
            function toggleStars(practiceId) {{
                const starsDiv = document.getElementById('stars-' + practiceId);
                const btn = document.getElementById('starsBtn-' + practiceId);
                starsDiv.classList.toggle('stars-hidden');
                btn.textContent = starsDiv.classList.contains('stars-hidden') ? 'Show Importance' : 'Hide Importance';
            }}
            
            function toggleSubjectTopic(practiceId) {{
                const subjectTopicDiv = document.getElementById('subjectTopic-' + practiceId);
                const btn = document.getElementById('subjectTopicBtn-' + practiceId);
                subjectTopicDiv.classList.toggle('subject-topic-hidden');
                btn.textContent = subjectTopicDiv.classList.contains('subject-topic-hidden') ? 'Show Subject & Topic' : 'Hide Subject & Topic';
            }}
            
            function toggleAnswer(practiceId) {{
                const answerDiv = document.getElementById('answer-' + practiceId);
                const btn = document.getElementById('answerBtn-' + practiceId);
                answerDiv.classList.toggle('answer-hidden');
                btn.textContent = answerDiv.classList.contains('answer-hidden') ? 'Show Answer' : 'Hide Answer';
            }}
            
            function togglePracticeForm() {{
                const form = document.getElementById('practiceForm');
                const btn = document.getElementById('addPracticeBtn');
                form.classList.toggle('show');
                btn.textContent = form.classList.contains('show') ? 'Hide Form' : 'Add New Practice Item';
            }}
        </script>
    </head>
    <body>
        {navbar}
        <h1>Spaced Repetition Practice</h1>
        <p>Practice and reinforce your learning with spaced repetition.</p>
        
        <h2>Filter Questions</h2>
        <form method="get" style="margin-bottom: 20px; padding: 15px; background-color: #f9f9f9; border-radius: 4px;">
            <label for="subject" style="margin-right: 10px; font-weight: bold;">Subject:</label>
            <select name="subject" id="subject" style="padding: 8px; margin-right: 20px;">
                <option value="">All Subjects</option>
                {'\n'.join([f'<option value="{subject["subject"]}" {"selected" if filter_subject == subject["subject"] else ""}>{subject["subject"]}</option>' for subject in all_subjects])}
            </select>
            
            <label for="topic" style="margin-right: 10px; font-weight: bold;">Topic:</label>
            <select name="topic" id="topic" style="padding: 8px; margin-right: 20px;">
                <option value="">All Topics</option>
                {'\n'.join([f'<option value="{topic["topic"]}" {"selected" if filter_topic == topic["topic"] else ""}>{topic["topic"]}</option>' for topic in all_topics])}
            </select>
            
            <label for="filter" style="margin-right: 10px; font-weight: bold;">Filter Type:</label>
            <select name="filter" id="filter" style="padding: 8px; margin-right: 20px;">
                <option value="all" {"selected" if filter_type == "all" else ""}>All Dates</option>
                <option value="before" {"selected" if filter_type == "before" else ""}>Before Date</option>
                <option value="after" {"selected" if filter_type == "after" else ""}>After Date</option>
                <option value="on" {"selected" if filter_type == "on" else ""}>On Date</option>
            </select>
            
            <label for="date" style="margin-right: 10px; font-weight: bold;">Date:</label>
            <input type="date" name="date" id="date" value="{filter_date}" style="padding: 8px; margin-right: 20px;">
            
            <label for="stars" style="margin-right: 10px; font-weight: bold;">Stars:</label>
            <select name="stars" id="stars" style="padding: 8px; margin-right: 20px;">
                <option value="">All Star Ratings</option>
                <option value="0" {"selected" if filter_stars == "0" else ""}>No Stars (0)</option>
                <option value="1" {"selected" if filter_stars == "1" else ""}>⭐ (1)</option>
                <option value="2" {"selected" if filter_stars == "2" else ""}>⭐⭐ (2)</option>
                <option value="3" {"selected" if filter_stars == "3" else ""}>⭐⭐⭐ (3)</option>
                <option value="4" {"selected" if filter_stars == "4" else ""}>⭐⭐⭐⭐ (4)</option>
                <option value="5" {"selected" if filter_stars == "5" else ""}>⭐⭐⭐⭐⭐ (5)</option>
            </select>
            
            <label for="q" style="margin-right: 10px; font-weight: bold;">Search:</label>
            <input type="text" name="q" id="q" value="{filter_q}" placeholder="Search question or answer" style="padding: 8px; margin-right: 20px;">
            <button type="submit" style="padding: 8px 16px; background-color: #2196F3; color: white; border: none; border-radius: 4px; cursor: pointer;">Filter</button>
            <a href="/practice" style="padding: 8px 16px; background-color: #999; color: white; text-decoration: none; border-radius: 4px; display: inline-block; margin-left: 10px;">Clear Filter</a>
        </form>
        
        <button id="addPracticeBtn" onclick="togglePracticeForm()">Add New Practice Item</button>
        
        <form id="practiceForm" method="post">
            <div class="form-group">
                <label for="subject">Subject:</label>
                <input type="text" name="subject" id="subject" placeholder="e.g., Mathematics, Biology" required>
            </div>
            <div class="form-group">
                <label for="topic">Topic:</label>
                <input type="text" name="topic" id="topic" placeholder="e.g., Algebra, Cells" required>
            </div>
            <div class="form-group">
                <label for="question">Question:</label>
                <textarea name="question" id="question" placeholder="Enter your question here..." required></textarea>
            </div>
            <div class="form-group">
                <label for="answer">Answer:</label>
                <textarea name="answer" id="answer" placeholder="Enter the answer here..." required></textarea>
            </div>
            <button type="submit">Add Practice Item</button>
        </form>
        
        <h2>Practice Items:</h2>
        {practices_html}
        
        <!-- Pagination Controls -->
        <div style="margin-top: 20px; text-align: center;">
            <p>Page {page} of {total_pages} (Total: {total_practices} items)</p>
            <div>
                {f'<a href="/practice?page=1{("&" + params_query) if params_query else ""}" style="margin: 0 5px;">First</a>' if page > 1 else ''}
                {f'<a href="/practice?page={page-1}{("&" + params_query) if params_query else ""}" style="margin: 0 5px;">Previous</a>' if page > 1 else ''}
                <span style="margin: 0 10px;">Page {page}</span>
                {f'<a href="/practice?page={page+1}{("&" + params_query) if params_query else ""}" style="margin: 0 5px;">Next</a>' if page < total_pages else ''}
                {f'<a href="/practice?page={total_pages}{("&" + params_query) if params_query else ""}" style="margin: 0 5px;">Last</a>' if page < total_pages else ''}
            </div>
        </div>
    </body>
    </html>
    '''


if __name__ == '__main__':
    app.run(debug=True)


@app.route('/search-practice', methods=['GET'])
def search_practice():
    """Return JSON list of practices matching question or answer text."""
    q = request.args.get('q', '', type=str)
    conn = get_db_connection()
    results = []
    if q:
        like_q = f'%{q}%'
        rows = conn.execute(
            'SELECT * FROM spaced_repetition WHERE question LIKE ? OR answer LIKE ? ORDER BY date ASC, stars ASC',
            (like_q, like_q)
        ).fetchall()
        results = [dict(r) for r in rows]
    conn.close()
    return jsonify(results)
