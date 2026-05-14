import { useState, useEffect } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL

// localStorage key for the pantry persistence
const PANTRY_KEY = 'fridge-pantry'

// denylist non food
const DETECTION_DENYLIST = new Set([
  'refrigerator', 'dining table', 'person', 'chair', 'couch', 'bed',
  'tv', 'laptop', 'mouse', 'keyboard', 'cell phone', 'book', 'clock',
  'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush',
  'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
])

const QUICK_ADDS = [
  'olive oil', 'salt', 'pepper', 'eggs', 'butter',
  'garlic', 'onion', 'flour', 'sugar', 'milk',
]

const PREFERENCES = [
  'vegetarian', 'vegan', 'quick (under 30 min)',
  'italian', 'asian', 'mexican', 'comfort food', 'persian', 'afghan',
]

function loadPantry() {
  try {
    const raw = localStorage.getItem(PANTRY_KEY)
    const parsed = raw ? JSON.parse(raw) : null
    return Array.isArray(parsed) && parsed.length > 0 ? parsed : ['']
  } catch {
    return ['']
  }
}

function savePantry(ingredients) {
  try {
    const cleaned = ingredients.map(i => i.trim()).filter(Boolean)
    if (cleaned.length > 0) {
      localStorage.setItem(PANTRY_KEY, JSON.stringify(cleaned))
    } else {
      localStorage.removeItem(PANTRY_KEY)
    }
  } catch {}
}

export default function App() {
  const [mode, setMode] = useState('home')

  return (
    <div className="app">
      <header>
        <h1>🥑 Fridge Recipes</h1>
        {mode !== 'home' && (
          <button onClick={() => setMode('home')} className="back-button">
            ← Back
          </button>
        )}
      </header>

      {mode === 'home' && <HomeView onSelect={setMode} />}
      {mode === 'type' && <TypeIngredientsView />}
      {mode === 'photo' && <PhotoView />}
    </div>
  )
}

function HomeView({ onSelect }) {
  return (
    <div className="home">
      <p className="tagline">What's in your kitchen today?</p>

      <button className="option-card" onClick={() => onSelect('type')}>
        <span className="option-emoji">✏️</span>
        <span className="option-title">Type ingredients</span>
        <span className="option-desc">List what you have, get recipes.</span>
      </button>

      <button className="option-card" onClick={() => onSelect('photo')}>
        <span className="option-emoji">📷</span>
        <span className="option-title">Snap a photo</span>
        <span className="option-desc">Show me your fridge. I'll spot what's in it.</span>
      </button>
    </div>
  )
}

function TypeIngredientsView() {
  const [ingredients, setIngredients] = useState(() => loadPantry())
  const [preferences, setPreferences] = useState([])
  const [recipes, setRecipes] = useState(null)
  const [status, setStatus] = useState('editing')
  const [error, setError] = useState(null)

  useEffect(() => {
    savePantry(ingredients)
  }, [ingredients])

  function addItem(name) {
    const exists = ingredients.some(i => i.trim().toLowerCase() === name.toLowerCase())
    if (exists) return

    const firstEmpty = ingredients.findIndex(i => i.trim() === '')
    if (firstEmpty >= 0) {
      const next = [...ingredients]
      next[firstEmpty] = name
      setIngredients(next)
    } else {
      setIngredients([...ingredients, name])
    }
  }

  async function generateRecipes() {
    const cleaned = ingredients.map(i => i.trim()).filter(Boolean)
    if (cleaned.length === 0) {
      setError('Add at least one ingredient')
      return
    }

    setStatus('cooking')
    setError(null)
    setRecipes(null)
    try {
      const resp = await fetch(`${API_URL}recipes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ingredients: cleaned,
          preferences: preferences.length > 0 ? preferences : undefined,
        }),
      })
      if (!resp.ok) throw new Error('Failed to generate recipes')
      const data = await resp.json()
      setRecipes(data.recipes)
      setStatus('done')
    } catch (err) {
      setError(err.message)
      setStatus('editing')
    }
  }

  return (
    <div>
      <p className="hint">List ingredients with quantities, one per row.</p>
      <IngredientEditor
        ingredients={ingredients}
        onChange={setIngredients}
        disabled={status === 'cooking'}
        placeholder="e.g. 2 apples"
      />

      <SuggestionChips items={QUICK_ADDS} onAdd={addItem} />

      <PreferenceToggles selected={preferences} onChange={setPreferences} />

      <button
        type="button"
        onClick={generateRecipes}
        disabled={status === 'cooking' || ingredients.every(i => !i.trim())}
        className="generate-btn"
      >
        {status === 'cooking' ? 'Working…' : 'Generate recipes'}
      </button>

      {status === 'cooking' && <div className="status">🍳 Generating recipes…</div>}
      {error && <div className="error">⚠️ {error}</div>}
      {recipes && (
        <RecipeList recipes={recipes} onRegenerate={generateRecipes} disabled={status === 'cooking'} />
      )}
    </div>
  )
}

function PhotoView() {
  const [phase, setPhase] = useState('select')
  const [previewUrl, setPreviewUrl] = useState(null)
  const [scanId, setScanId] = useState(null)
  const [ingredients, setIngredients] = useState([])
  const [preferences, setPreferences] = useState([])
  const [recipes, setRecipes] = useState(null)
  const [error, setError] = useState(null)

  async function handleFileChange(e) {
    const file = e.target.files[0]
    if (!file) return

    setPreviewUrl(URL.createObjectURL(file))
    setError(null)
    setRecipes(null)
    setPhase('analyzing')

    try {
      const presignResp = await fetch(`${API_URL}uploads/presign`, { method: 'POST' })
      const { scan_id, upload_url } = await presignResp.json()
      setScanId(scan_id)

      const uploadResp = await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': 'image/jpeg' },
      })
      if (!uploadResp.ok) throw new Error('Upload to S3 failed')

      const result = await pollForResult(scan_id)
      // Filter denylisted detections (furniture, electronics, body parts...)
      const detected = Object.entries(result.summary)
        .filter(([name]) => !DETECTION_DENYLIST.has(name.toLowerCase()))
        .map(([name, count]) => (count > 1 ? `${count} ${name}` : name))
      setIngredients(detected.length > 0 ? detected : [''])
      setPhase('editing')
    } catch (err) {
      setError(err.message)
      setPhase('select')
    }
  }

  async function generateRecipes() {
    const cleaned = ingredients.map(i => i.trim()).filter(Boolean)
    if (cleaned.length === 0) {
      setError('Add at least one ingredient')
      return
    }

    setPhase('cooking')
    setError(null)
    setRecipes(null)
    try {
      const resp = await fetch(`${API_URL}recipes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ingredients: cleaned,
          scan_id: scanId,
          preferences: preferences.length > 0 ? preferences : undefined,
        }),
      })
      if (!resp.ok) throw new Error('Failed to generate recipes')
      const data = await resp.json()
      setRecipes(data.recipes)
      setPhase('done')
    } catch (err) {
      setError(err.message)
      setPhase('editing')
    }
  }

  return (
    <div>
      {phase === 'select' && (
        <label className="capture-button">
          📷  Take or pick a photo
          <input
            type="file"
            accept="image/*"
            capture="environment"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
        </label>
      )}

      {previewUrl && <img className="preview" src={previewUrl} alt="" />}

      {phase === 'analyzing' && (
        <div className="status">🔍 Spotting ingredients…</div>
      )}

      {(phase === 'editing' || phase === 'cooking' || phase === 'done') && (
        <>
          <h2 className="section-title">Spotted in your photo</h2>
          <p className="hint">Add, edit, or remove anything before cooking.</p>
          <IngredientEditor
            ingredients={ingredients}
            onChange={setIngredients}
            disabled={phase === 'cooking'}
            placeholder="e.g. 2 apples"
          />

          <PreferenceToggles selected={preferences} onChange={setPreferences} />

          <button
            type="button"
            onClick={generateRecipes}
            disabled={phase === 'cooking' || ingredients.every(i => !i.trim())}
            className="generate-btn"
          >
            {phase === 'cooking' ? 'Working…' : 'Generate recipes'}
          </button>
        </>
      )}

      {phase === 'cooking' && <div className="status">🍳 Generating recipes…</div>}
      {error && <div className="error">⚠️ {error}</div>}
      {recipes && (
        <RecipeList recipes={recipes} onRegenerate={generateRecipes} disabled={phase === 'cooking'} />
      )}
    </div>
  )
}

function IngredientEditor({ ingredients, onChange, disabled, placeholder }) {
  function update(index, value) {
    const next = [...ingredients]
    next[index] = value
    onChange(next)
  }
  function remove(index) {
    const next = ingredients.filter((_, i) => i !== index)
    onChange(next.length > 0 ? next : [''])
  }
  function add() {
    onChange([...ingredients, ''])
  }

  return (
    <div className="ingredient-editor">
      {ingredients.map((ing, i) => (
        <div key={i} className="ingredient-row">
          <input
            type="text"
            value={ing}
            onChange={(e) => update(i, e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
          />
          <button
            type="button"
            onClick={() => remove(i)}
            disabled={disabled}
            className="remove-btn"
            aria-label="Remove"
          >×</button>
        </div>
      ))}
      <button type="button" onClick={add} className="add-btn" disabled={disabled}>
        + Add ingredient
      </button>
    </div>
  )
}

function SuggestionChips({ items, onAdd }) {
  return (
    <div className="chips-block">
      <p className="chips-label">Common pantry items</p>
      <div className="chips-row">
        {items.map((item) => (
          <button
            key={item}
            type="button"
            className="chip"
            onClick={() => onAdd(item)}
          >
            + {item}
          </button>
        ))}
      </div>
    </div>
  )
}

function PreferenceToggles({ selected, onChange }) {
  function toggle(pref) {
    if (selected.includes(pref)) {
      onChange(selected.filter(p => p !== pref))
    } else {
      onChange([...selected, pref])
    }
  }

  return (
    <div className="chips-block">
      <p className="chips-label">Preferences (optional)</p>
      <div className="chips-row">
        {PREFERENCES.map((pref) => (
          <button
            key={pref}
            type="button"
            className={`chip ${selected.includes(pref) ? 'chip-on' : ''}`}
            onClick={() => toggle(pref)}
          >
            {pref}
          </button>
        ))}
      </div>
    </div>
  )
}

function RecipeList({ recipes, onRegenerate, disabled }) {
  return (
    <section className="recipes">
      <div className="recipes-header">
        <h2 className="section-title">Try cooking</h2>
        <button
          type="button"
          onClick={onRegenerate}
          disabled={disabled}
          className="regenerate-btn"
        >
          🔄 Regenerate
        </button>
      </div>
      {recipes.map((r, i) => (
        <article key={i} className="recipe">
          <h3>{r.title}</h3>
          <h4>Ingredients</h4>
          <ul>{r.ingredients.map((ing, j) => <li key={j}>{ing}</li>)}</ul>
          <h4>Steps</h4>
          <ol>{r.steps.map((s, j) => <li key={j}>{s}</li>)}</ol>
        </article>
      ))}
    </section>
  )
}

async function pollForResult(scanId) {
  for (let i = 0; i < 30; i++) {
    const resp = await fetch(`${API_URL}scans/${scanId}`)
    if (resp.ok) {
      const data = await resp.json()
      if (data.status === 'ready') return data
    }
    await new Promise(r => setTimeout(r, 1000))
  }
  throw new Error('Scan timed out')
}