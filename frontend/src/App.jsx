import { useEffect, useMemo, useState } from 'react'

const emptyForm = {
  patient_name: '',
  clinician: '',
  appointment_date: '',
  start_clock: '',
  duration: '',
}

const emptyRescheduleForm = {
  clinician: '',
  appointment_date: '',
  start_clock: '',
  duration: '',
}

const startTimeOptions = Array.from({ length: 96 }, (_, index) => {
  const hour = String(Math.floor(index / 4)).padStart(2, '0')
  const minute = String((index % 4) * 15).padStart(2, '0')
  return `${hour}:${minute}`
})

async function readJson(response) {
  const data = await response.json()
  if (!response.ok) {
    const message =
      typeof data.detail === 'string'
        ? data.detail
        : data.detail?.[0]?.msg || 'Request failed'
    throw new Error(message)
  }
  return data
}

function formatDateTime(value) {
  return new Date(value).toLocaleString([], {
    dateStyle: 'medium',
    timeStyle: 'short',
  })
}

function formatDuration(value) {
  return value === 60 ? '1 hour' : '30 minutes'
}

function App() {
  const [schedules, setSchedules] = useState([])
  const [clinicians, setClinicians] = useState([])
  const [doctorFilter, setDoctorFilter] = useState('')
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [deletingId, setDeletingId] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [rescheduleForm, setRescheduleForm] = useState(emptyRescheduleForm)
  const [updating, setUpdating] = useState(false)
  const [message, setMessage] = useState('')

  const editingSchedule = schedules.find((schedule) => schedule.id === editingId)

  const visibleSchedules = useMemo(
    () =>
      schedules
        .filter((schedule) => !doctorFilter || schedule.clinician === doctorFilter)
        .slice()
        .sort((first, second) => new Date(first.start_time) - new Date(second.start_time)),
    [doctorFilter, schedules],
  )

  useEffect(() => {
    async function loadData() {
      try {
        const [scheduleResponse, clinicianResponse] = await Promise.all([
          fetch('/api/schedules'),
          fetch('/api/clinicians'),
        ])
        const [scheduleData, clinicianData] = await Promise.all([
          readJson(scheduleResponse),
          readJson(clinicianResponse),
        ])
        setSchedules(scheduleData)
        setClinicians(clinicianData)
      } catch (error) {
        setMessage(error.message || 'Could not load scheduling data')
      } finally {
        setLoading(false)
      }
    }

    loadData()
  }, [])

  function updateField(event) {
    setForm((current) => ({ ...current, [event.target.name]: event.target.value }))
  }

  function updateRescheduleField(event) {
    setRescheduleForm((current) => ({
      ...current,
      [event.target.name]: event.target.value,
    }))
  }

  async function createSchedule(event) {
    event.preventDefault()
    setMessage('')

    const startTime = new Date(`${form.appointment_date}T${form.start_clock}`)
    const duration = Number(form.duration)

    if (
      ![0, 15, 30, 45].includes(startTime.getMinutes()) ||
      startTime.getSeconds() !== 0
    ) {
      setMessage('Start time must use a 15-minute interval')
      return
    }

    if (![30, 60].includes(duration)) {
      setMessage('Schedule duration must be 30 or 60 minutes')
      return
    }

    setSubmitting(true)
    try {
      const payload = {
        patient_name: form.patient_name,
        clinician: form.clinician,
        start_time: `${form.appointment_date}T${form.start_clock}:00`,
        duration,
      }
      const response = await fetch('/api/schedules', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const created = await readJson(response)
      setSchedules((current) => [...current, created])
      setForm(emptyForm)
      setMessage('Schedule created')
    } catch (error) {
      setMessage(error.message || 'Could not create schedule')
    } finally {
      setSubmitting(false)
    }
  }

  async function cancelSchedule(scheduleId) {
    setMessage('')
    setDeletingId(scheduleId)

    try {
      const response = await fetch(`/api/schedules/${scheduleId}`, { method: 'DELETE' })
      if (!response.ok) await readJson(response)

      setSchedules((current) => current.filter((schedule) => schedule.id !== scheduleId))
      if (editingId === scheduleId) setEditingId(null)
      setMessage('Schedule canceled')
    } catch (error) {
      setMessage(error.message || 'Could not cancel schedule')
    } finally {
      setDeletingId(null)
    }
  }

  function beginReschedule(schedule) {
    const [appointmentDate, time] = schedule.start_time.split('T')
    setEditingId(schedule.id)
    setRescheduleForm({
      clinician: schedule.clinician,
      appointment_date: appointmentDate,
      start_clock: time.slice(0, 5),
      duration: String(schedule.duration),
    })
    setMessage('')
  }

  function discardReschedule() {
    setEditingId(null)
    setRescheduleForm(emptyRescheduleForm)
    setMessage('')
  }

  async function reschedule(event) {
    event.preventDefault()
    setMessage('')
    setUpdating(true)

    try {
      const response = await fetch(`/api/schedules/${editingId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          clinician: rescheduleForm.clinician,
          start_time: `${rescheduleForm.appointment_date}T${rescheduleForm.start_clock}:00`,
          duration: Number(rescheduleForm.duration),
        }),
      })
      const updated = await readJson(response)
      setSchedules((current) =>
        current.map((schedule) => (schedule.id === updated.id ? updated : schedule)),
      )
      setEditingId(null)
      setRescheduleForm(emptyRescheduleForm)
      setMessage('Schedule updated')
    } catch (error) {
      setMessage(error.message || 'Could not reschedule appointment')
    } finally {
      setUpdating(false)
    }
  }

  return (
    <main className="page">
      <header>
        <p className="eyebrow">Clinic operations</p>
        <h1>Clinician scheduling</h1>
        <p className="subtitle">Create appointments and review the current schedule.</p>
      </header>

      <section className="panel" aria-labelledby="create-heading">
        <h2 id="create-heading">New schedule</h2>
        <p className="subtitle">
          Start on :00, :15, :30, or :45 and choose a 30- or 60-minute slot.
        </p>
        <form className="schedule-form" onSubmit={createSchedule}>
          <label>
            Patient name
            <input
              name="patient_name"
              value={form.patient_name}
              onChange={updateField}
              required
            />
          </label>
          <label>
            Clinician
            <select name="clinician" value={form.clinician} onChange={updateField} required>
              <option value="">Select a clinician</option>
              {clinicians.map((clinician) => (
                <option key={clinician} value={clinician}>
                  {clinician}
                </option>
              ))}
            </select>
          </label>
          <label>
            Appointment date
            <input
              type="date"
              name="appointment_date"
              value={form.appointment_date}
              onChange={updateField}
              required
            />
          </label>
          <label>
            Start time
            <select name="start_clock" value={form.start_clock} onChange={updateField} required>
              <option value="">Select a start time</option>
              {startTimeOptions.map((time) => (
                <option key={time} value={time}>
                  {time}
                </option>
              ))}
            </select>
          </label>
          <label>
            Duration
            <select name="duration" value={form.duration} onChange={updateField} required>
              <option value="">Select a duration</option>
              <option value="30">30 minutes</option>
              <option value="60">1 hour</option>
            </select>
          </label>
          <button type="submit" disabled={submitting || loading}>
            {submitting ? 'Creating...' : 'Create schedule'}
          </button>
        </form>
        {message && !editingSchedule && (
          <p className="message" role="status">
            {message}
          </p>
        )}
      </section>

      <section className="panel" aria-labelledby="schedule-heading">
        <div className="section-heading">
          <h2 id="schedule-heading">Current schedules</h2>
          <div className="schedule-controls">
            <label className="doctor-filter">
              Filter by doctor
              <select value={doctorFilter} onChange={(event) => setDoctorFilter(event.target.value)}>
                <option value="">All doctors</option>
                {clinicians.map((clinician) => (
                  <option key={clinician} value={clinician}>
                    {clinician}
                  </option>
                ))}
              </select>
            </label>
            <span>{visibleSchedules.length} shown</span>
          </div>
        </div>
        {editingSchedule && (
          <form className="reschedule-form" onSubmit={reschedule}>
            <h3>Reschedule {editingSchedule.patient_name}</h3>
            <label>
              Clinician
              <select
                name="clinician"
                value={rescheduleForm.clinician}
                onChange={updateRescheduleField}
                required
              >
                {clinicians.map((clinician) => (
                  <option key={clinician} value={clinician}>
                    {clinician}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Appointment date
              <input
                type="date"
                name="appointment_date"
                value={rescheduleForm.appointment_date}
                onChange={updateRescheduleField}
                required
              />
            </label>
            <label>
              Start time
              <select
                name="start_clock"
                value={rescheduleForm.start_clock}
                onChange={updateRescheduleField}
                required
              >
                {startTimeOptions.map((time) => (
                  <option key={time} value={time}>
                    {time}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Duration
              <select
                name="duration"
                value={rescheduleForm.duration}
                onChange={updateRescheduleField}
                required
              >
                <option value="30">30 minutes</option>
                <option value="60">1 hour</option>
              </select>
            </label>
            <div className="form-actions">
              <button type="submit" disabled={updating}>
                {updating ? 'Saving...' : 'Save changes'}
              </button>
              <button
                className="secondary-button"
                type="button"
                onClick={discardReschedule}
                disabled={updating}
              >
                Discard
              </button>
            </div>
            {message && (
              <p className="message" role="status">
                {message}
              </p>
            )}
          </form>
        )}
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Patient</th>
                <th>Clinician</th>
                <th>Start</th>
                <th>Duration</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleSchedules.map((schedule) => (
                <tr key={schedule.id}>
                  <td>{schedule.patient_name}</td>
                  <td>{schedule.clinician}</td>
                  <td>{formatDateTime(schedule.start_time)}</td>
                  <td>{formatDuration(schedule.duration)}</td>
                  <td>
                    <div className="row-actions">
                      <button
                        className="secondary-button"
                        type="button"
                        onClick={() => beginReschedule(schedule)}
                        disabled={updating}
                      >
                        Reschedule
                      </button>
                      <button
                        className="cancel-button"
                        type="button"
                        onClick={() => cancelSchedule(schedule.id)}
                        disabled={deletingId === schedule.id}
                      >
                        {deletingId === schedule.id ? 'Canceling...' : 'Cancel'}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {!loading && visibleSchedules.length === 0 && (
                <tr>
                  <td className="empty" colSpan="5">
                    {doctorFilter ? 'No schedules for this doctor.' : 'No schedules yet.'}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  )
}

export default App

