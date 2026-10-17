import { COURSE_MAP, COURSES } from '../data.js'

export default function CoursesTab() {
  return (
    <div className="stack">
      <div className="course-cards">
        {COURSES.map((c, i) => (
          <div key={c.short} className="card course">
            <div className="course-num">Course {i + 1}</div>
            <h3>{c.full}</h3>
            <p className="muted small">Infosys Springboard (Udemy) · {c.duration} · {c.level}</p>
            <p className="small">{c.focus}</p>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>How each course shows up in StudyPilot</h2>
        <table className="table">
          <thead><tr><th>Course</th><th>Concept learned</th><th>Where it's used in StudyPilot</th></tr></thead>
          <tbody>
            {COURSE_MAP.map(([course, concept, where], i) => (
              <tr key={i}>
                <td><span className={`course-tag c${course + 1}`}>{COURSES[course].short}</span></td>
                <td>{concept}</td>
                <td>{where}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
