import { type FormEvent, useEffect, useMemo, useState } from "react";

import katex from "katex";
import "katex/dist/katex.min.css";

import "./App.css";

import Graph from "./components/Graph";

import { sampleLatex, type Point } from "./math/sampleFunction";

import { rmse } from "./math/scoreEquation";

import { normalizeInput, type InputMode } from "./math/normalizeInput";

const API =
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.PROD ? "" : "http://localhost:8000");

type Challenge = {
  id: number;
  date: string;

  domain: {
    min: number;
    max: number;
  };

  range: {
    min: number;
    max: number;
  };

  archived?: boolean;
  target_expr?: string;
  target_latex?: string;
  target_points: Point[];
};

type User = {
  id: number;
  username: string;
  avatar_url: string | null;
};

type LeaderboardEntry = {
  rank: number;
  username: string;
  avatar_url: string | null;
  cost: number;
  error: number;
  mode: string;
  equation?: string;
};

function challengeOptionLabel(date: string, today: string) {
  const difference = Math.round(
    (Date.parse(`${date}T00:00:00Z`) - Date.parse(`${today}T00:00:00Z`)) /
      86400000,
  );

  if (difference === 0) return `Today · ${date}`;
  if (difference === -1) return `Yesterday · ${date}`;
  if (difference === 1) return `Tomorrow · ${date}`;
  return date;
}

function formatCountdown(milliseconds: number) {
  const totalSeconds = Math.max(0, Math.floor(milliseconds / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  return [hours, minutes, seconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

export default function App() {
  const [challenge, setChallenge] = useState<Challenge | null>(null);

  const [user, setUser] = useState<User | null>(null);

  const [mode, setMode] = useState<InputMode>("basic");

  const [input, setInput] = useState("sin(x)");

  const [loadError, setLoadError] = useState<string | null>(null);

  const [submitMessage, setSubmitMessage] = useState("");

  const [submitting, setSubmitting] = useState(false);

  const [showLeaderboard, setShowLeaderboard] = useState(false);

  const [loginPromptOpen, setLoginPromptOpen] = useState(false);

  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);

  const [leaderboardTotal, setLeaderboardTotal] = useState(0);

  const [leaderboardOffset, setLeaderboardOffset] = useState(0);

  const [availableChallenges, setAvailableChallenges] = useState<Challenge[]>(
    [],
  );

  const [leaderboardChallenge, setLeaderboardChallenge] =
    useState<Challenge | null>(null);

  const [leaderboardDate, setLeaderboardDate] = useState<string | null>(null);

  const [copiedFormat, setCopiedFormat] = useState<string | null>(null);

  const [equationFormat, setEquationFormat] = useState<
    "text" | "latex" | "wolfram"
  >("text");

  const [selectedEquationRanks, setSelectedEquationRanks] = useState<number[]>(
    [],
  );

  const [clock, setClock] = useState(() => Date.now());

  const [showAbout, setShowAbout] = useState(false);

  const [accountMenuOpen, setAccountMenuOpen] = useState(false);

  const [displayNameInput, setDisplayNameInput] = useState("");

  const [displayNameMessage, setDisplayNameMessage] = useState("");

  const [savingDisplayName, setSavingDisplayName] = useState(false);

  async function loadLeaderboard(
    date = leaderboardDate ?? challenge?.date,
    offset = leaderboardOffset,
  ) {
    if (!date) {
      return;
    }

    try {
      const response = await fetch(
        `${API}/api/challenge/${date}/leaderboard?limit=100&offset=${offset}`,
        {
          credentials: "include",
        },
      );

      if (!response.ok) {
        return;
      }

      const data = await response.json();

      setLeaderboard(data.entries ?? []);
      setLeaderboardTotal(data.total ?? 0);
      setLeaderboardOffset(data.offset ?? offset);
      setLeaderboardChallenge(data.challenge ?? null);
    } catch (error) {
      console.error("Could not load leaderboard:", error);
    }
  }

  async function copyEquation(format: string, value: string) {
    await navigator.clipboard.writeText(value);
    setCopiedFormat(format);
    window.setTimeout(() => setCopiedFormat(null), 1400);
  }

  async function saveDisplayName(event: FormEvent) {
    event.preventDefault();
    setSavingDisplayName(true);
    setDisplayNameMessage("");

    try {
      const response = await fetch(`${API}/api/me`, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayNameInput }),
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "Could not save display name");
      }

      setUser(data.user);
      setDisplayNameInput(data.user.username);
      setDisplayNameMessage("Saved");
    } catch (error) {
      setDisplayNameMessage(
        error instanceof Error ? error.message : "Could not save display name",
      );
    } finally {
      setSavingDisplayName(false);
    }
  }

  useEffect(() => {
    async function load() {
      try {
        const bootstrapResponse = await fetch(`${API}/api/bootstrap`, {
          credentials: "include",
        });

        if (!bootstrapResponse.ok) {
          throw new Error(
            `Bootstrap request failed: ${bootstrapResponse.status}`,
          );
        }

        const data = await bootstrapResponse.json();
        const challengeData = data.challenge;

        setChallenge(challengeData);
        setAvailableChallenges(data.challenges ?? []);
        setLeaderboard(data.leaderboard?.entries ?? []);
        setLeaderboardTotal(data.leaderboard?.total ?? 0);
        setLeaderboardOffset(data.leaderboard?.offset ?? 0);
        setLeaderboardChallenge(data.leaderboard?.challenge ?? null);
        setLeaderboardDate(challengeData.date);

        if (data.me?.authenticated) {
          setUser(data.me.user);
          setDisplayNameInput(data.me.user.username);
        }
      } catch (error) {
        console.error(error);

        setLoadError("Could not load today's challenge.");
      }
    }

    load();
  }, []);

  useEffect(() => {
    if (!showLeaderboard) {
      return;
    }

    const updateClock = () => setClock(Date.now());
    updateClock();
    const interval = window.setInterval(updateClock, 1000);

    return () => window.clearInterval(interval);
  }, [showLeaderboard]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") {
        return;
      }

      setShowLeaderboard(false);
      setShowAbout(false);
      setLoginPromptOpen(false);
    }

    window.addEventListener("keydown", onKeyDown);

    return () => {
      window.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  const playerLatex = useMemo(() => normalizeInput(input, mode), [input, mode]);

  const playerPoints = useMemo(() => {
    if (!challenge) {
      return [];
    }

    return sampleLatex(playerLatex, challenge.domain.min, challenge.domain.max);
  }, [playerLatex, challenge]);

  const previewError = useMemo(() => {
    if (!challenge) {
      return Infinity;
    }

    return rmse(challenge.target_points, playerPoints);
  }, [challenge, playerPoints]);

  const previewHtml = useMemo(() => {
    try {
      return katex.renderToString(playerLatex || " ", {
        displayMode: true,
        throwOnError: false,
        trust: false,
      });
    } catch {
      return "";
    }
  }, [playerLatex]);

  async function submitScore() {
    if (!user) {
      setAccountMenuOpen(false);
      setShowAbout(false);
      setShowLeaderboard(false);
      setLoginPromptOpen(true);
      return;
    }

    setSubmitting(true);
    setSubmitMessage("");

    try {
      const response = await fetch(`${API}/api/challenge/today/submit`, {
        method: "POST",

        credentials: "include",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          equation: input,
          mode,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "Submission failed");
      }

      let message =
        `Submitted — cost ${data.cost}` + ` · error ${data.error.toFixed(6)}`;

      if (data.on_pareto_frontier && data.display_position) {
        message += ` · frontier position #${data.display_position}`;
      } else {
        message += " · not on the Pareto frontier";
      }

      setSubmitMessage(message);

      await loadLeaderboard(challenge?.date, 0);
    } catch (error) {
      setSubmitMessage(
        error instanceof Error ? error.message : "Submission failed",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function logout() {
    await fetch(`${API}/api/logout`, {
      method: "POST",
      credentials: "include",
    });

    setUser(null);
    setAccountMenuOpen(false);
    setSubmitMessage("");
  }

  async function openLeaderboard() {
    if (!challenge) {
      return;
    }

    setAccountMenuOpen(false);
    setShowAbout(false);
    setLoginPromptOpen(false);
    setShowLeaderboard(true);
    const date = leaderboardDate ?? challenge.date;
    if (leaderboardChallenge?.date !== date) {
      await loadLeaderboard(date, leaderboardOffset);
    }
  }

  async function browseLeaderboardDate(date: string) {
    setLeaderboardDate(date);
    setLeaderboardOffset(0);
    setEquationFormat("text");
    setSelectedEquationRanks([]);
    await loadLeaderboard(date, 0);
  }

  async function browseLeaderboardStep(step: number) {
    const currentDate = leaderboardDate ?? challenge?.date;
    const currentIndex = availableChallenges.findIndex(
      (day) => day.date === currentDate,
    );
    const nextDay = availableChallenges[currentIndex + step];

    if (nextDay) {
      await browseLeaderboardDate(nextDay.date);
    }
  }

  const selectedEquation =
    equationFormat === "latex"
      ? leaderboardChallenge?.target_latex
      : equationFormat === "wolfram"
        ? leaderboardChallenge?.target_expr?.replace(/\*\*/g, "^")
        : leaderboardChallenge?.target_expr;

  const currentLeaderboardIndex = availableChallenges.findIndex(
    (day) => day.date === (leaderboardDate ?? challenge?.date),
  );

  const nextEquationCountdown = useMemo(() => {
    const current = new Date(clock);
    const nextUtcMidnight = Date.UTC(
      current.getUTCFullYear(),
      current.getUTCMonth(),
      current.getUTCDate() + 1,
    );

    return formatCountdown(nextUtcMidnight - clock);
  }, [clock]);

  function openAbout() {
    setAccountMenuOpen(false);
    setShowLeaderboard(false);
    setLoginPromptOpen(false);
    setShowAbout(true);
  }

  if (loadError) {
    return (
      <main className="game-board">
        <div className="page-message">
          <h1>Equation Golf</h1>
          <p>{loadError}</p>
        </div>
      </main>
    );
  }

  if (!challenge) {
    return (
      <main className="game-board">
        <div className="page-message">
          <h1>Equation Golf</h1>
          <p>Loading today's challenge…</p>
        </div>
      </main>
    );
  }

  const initial = user?.username?.trim().charAt(0).toUpperCase() || "?";

  return (
    <main className="game-board">
      <header className="top-bar">
        <div>
          <div className="brand">Equation Golf</div>

          <div className="brand-subtitle">
            a daily exercise in mathematical approximation
          </div>
        </div>

        <div className="header-actions">
          <button
            type="button"
            className="header-link"
            onClick={openLeaderboard}
          >
            Leaderboard
          </button>

          {user ? (
            <details
              className="account-menu"
              open={accountMenuOpen}
              onToggle={(event) => setAccountMenuOpen(event.currentTarget.open)}
            >
              <summary
                className="account-trigger"
                aria-label={`Account menu for ${user.username}`}
              >
                {user.avatar_url ? (
                  <img src={user.avatar_url} alt="" />
                ) : (
                  <span>{initial}</span>
                )}
              </summary>

              <div className="account-hover-name">{user.username}</div>

              <div className="account-dropdown">
                <div className="account-name">{user.username}</div>

                <div className="account-provider">Signed in with Google</div>

                <div className="account-rule" />

                <form className="display-name-form" onSubmit={saveDisplayName}>
                  <label htmlFor="display-name">display name</label>
                  <input
                    id="display-name"
                    value={displayNameInput}
                    maxLength={50}
                    onChange={(event) =>
                      setDisplayNameInput(event.target.value)
                    }
                  />
                  <button
                    type="submit"
                    className="account-action"
                    disabled={savingDisplayName}
                  >
                    {savingDisplayName ? "Saving…" : "Save name"}
                  </button>
                  {displayNameMessage && (
                    <div className="display-name-message">
                      {displayNameMessage}
                    </div>
                  )}
                </form>

                <div className="account-rule" />

                <button
                  type="button"
                  className="account-action"
                  onClick={logout}
                >
                  Log out
                </button>
              </div>
            </details>
          ) : (
            <a className="header-link" href={`${API}/auth/google`}>
              Sign in
            </a>
          )}
        </div>
      </header>

      <article className="game-area">
        <figure className="graph-figure">
          <div className="graph-shell">
            <Graph
              target={challenge.target_points}
              player={playerPoints}
              domain={challenge.domain}
              range={challenge.range}
            />
          </div>

          <figcaption className="challenge-meta">
            <span>
              <strong>Daily challenge</strong>
              {" · "}
              {challenge.date}
            </span>

            <span className="meta-separator">/</span>

            <span>
              domain {challenge.domain.min}
              {" ≤ x ≤ "}
              {challenge.domain.max}
            </span>
          </figcaption>
        </figure>

        <section className="equation-area">
          <div className="section-heading">
            <span className="section-number">01</span>

            <div>
              <h2>Your approximation</h2>

              <p>Find an efficient expression that follows the target curve.</p>
            </div>
          </div>

          <div className="mode-switch">
            <button
              type="button"
              className={
                mode === "basic" ? "mode-button active" : "mode-button"
              }
              onClick={() => setMode("basic")}
            >
              Basic
            </button>

            <button
              type="button"
              className={
                mode === "latex" ? "mode-button active" : "mode-button"
              }
              onClick={() => setMode("latex")}
            >
              LaTeX
            </button>
          </div>

          <input
            className="equation-input"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            spellCheck={false}
            placeholder={mode === "basic" ? "sin(x) + 1" : "\\sin(x)+1"}
          />

          <div className="latex-preview">
            <div className="preview-title">rendered expression</div>

            <div
              className="preview-equation"
              dangerouslySetInnerHTML={{
                __html: previewHtml,
              }}
            />
          </div>

          <div className="stats">
            <div>
              <span>Error</span>
              <strong>
                {Number.isFinite(previewError)
                  ? previewError.toFixed(5)
                  : "invalid"}
              </strong>
            </div>
          </div>

          <button
            type="button"
            className="submit-button"
            onClick={submitScore}
            disabled={submitting}
          >
            {submitting
              ? "Submitting…"
              : user
                ? "Submit score"
                : "🔒 Submit score"}
          </button>

          {submitMessage && (
            <div className="submit-message">{submitMessage}</div>
          )}
        </section>
      </article>

      <button
        type="button"
        className="about-trigger"
        aria-label="About Equation Golf"
        title="About Equation Golf"
        onClick={openAbout}
      >
        <span aria-hidden="true">i</span>
      </button>

      {showAbout && (
        <div
          className="leaderboard-backdrop"
          onMouseDown={() => setShowAbout(false)}
        >
          <section
            className="leaderboard-modal about-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="about-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-topline">
              <div>
                <div className="modal-label">About the game</div>
                <h2 id="about-title">About Equation Golf</h2>
                <p>A small notebook for approximating curves.</p>
              </div>

              <button
                type="button"
                className="paper-close"
                aria-label="Close About"
                onClick={() => setShowAbout(false)}
              >
                ×
              </button>
            </div>

            <p>
              Equation Golf is a daily mathematical game. A hidden equation is
              sampled into a graph, and you write an expression whose curve
              follows it closely.
            </p>
            <p>
              Scores combine approximation error with expression cost. The
              leaderboard shows the Pareto frontier: a submission stays on it
              when no other submission is both cheaper and at least as accurate.
            </p>

            <section className="privacy-section">
              <h2>Data &amp; Privacy</h2>
              <p>Equation Golf uses Google Sign-In. It stores only:</p>
              <ul>
                <li>internal Equation Golf user ID</li>
                <li>Google&apos;s stable account identifier (sub)</li>
                <li>Google display name</li>
                <li>Google profile picture URL</li>
                <li>Equation Golf submissions and scores</li>
              </ul>
              <p>It does not store or access:</p>
              <ul>
                <li>Google email address or password</li>
                <li>Gmail, Drive, Contacts, or Calendar</li>
                <li>Google access, refresh, or ID tokens</li>
              </ul>
              <p>
                A session cookie keeps you signed in. Data is used only for
                authentication and leaderboard/submission functionality. Account
                and data deletion should be supported on request.
              </p>
            </section>
          </section>
        </div>
      )}

      {showLeaderboard && (
        <div
          className="leaderboard-backdrop"
          onMouseDown={() => setShowLeaderboard(false)}
        >
          <section
            className="leaderboard-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="leaderboard-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="modal-topline">
              <div>
                <div className="modal-label">Daily standings</div>

                <h2 id="leaderboard-title">Leaderboard</h2>

                <p>
                  {leaderboardChallenge?.date ?? challenge.date} · Pareto
                  leaderboard
                </p>
              </div>

              <button
                type="button"
                className="paper-close"
                aria-label="Close leaderboard"
                onClick={() => setShowLeaderboard(false)}
              >
                ×
              </button>
            </div>

            <div className="leaderboard-countdown" aria-live="polite">
              <span>next equation in</span>
              <strong>{nextEquationCountdown}</strong>
              <span>UTC</span>
            </div>

            <div className="leaderboard-day-picker">
              <button
                type="button"
                className="day-nav-button"
                aria-label="Previous challenge"
                disabled={currentLeaderboardIndex <= 0}
                onClick={() => browseLeaderboardStep(-1)}
              >
                ←
              </button>
              <div className="leaderboard-day-current">
                <span>challenge date</span>
                <strong>
                  {challengeOptionLabel(
                    leaderboardDate ?? challenge.date,
                    challenge.date,
                  )}
                </strong>
              </div>
              <button
                type="button"
                className="day-nav-button"
                aria-label="Next challenge"
                disabled={
                  currentLeaderboardIndex < 0 ||
                  currentLeaderboardIndex >= availableChallenges.length - 1
                }
                onClick={() => browseLeaderboardStep(1)}
              >
                →
              </button>
            </div>

            {leaderboardChallenge?.archived &&
              leaderboardChallenge.target_latex && (
                <div className="revealed-equation">
                  <div className="preview-title">revealed target equation</div>
                  <div
                    className="preview-equation"
                    dangerouslySetInnerHTML={{
                      __html: katex.renderToString(
                        leaderboardChallenge.target_latex,
                        {
                          displayMode: true,
                          throwOnError: false,
                          trust: false,
                        },
                      ),
                    }}
                  />
                  <div className="equation-export-picker">
                    <div className="equation-format-control">
                      <label htmlFor="equation-format">format</label>
                      <select
                        id="equation-format"
                        value={equationFormat}
                        onChange={(event) =>
                          setEquationFormat(
                            event.target.value as typeof equationFormat,
                          )
                        }
                      >
                        <option value="text">Plain text</option>
                        <option value="latex">LaTeX</option>
                        <option value="wolfram">Wolfram|Alpha</option>
                      </select>
                    </div>
                    <code>{selectedEquation}</code>
                    <div className="equation-export-actions">
                      <button
                        type="button"
                        className="text-button"
                        onClick={() =>
                          selectedEquation &&
                          copyEquation(equationFormat, selectedEquation)
                        }
                      >
                        {copiedFormat === equationFormat ? "Copied" : "Copy"}
                      </button>
                      <a
                        className="text-button"
                        href={`https://www.wolframalpha.com/input?i=${encodeURIComponent(leaderboardChallenge.target_expr?.replace(/\*\*/g, "^") ?? "")}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open in Wolfram|Alpha
                      </a>
                    </div>
                  </div>
                </div>
              )}

            {leaderboard.length === 0 ? (
              <div className="empty-leaderboard">
                <span>∅</span>
                No submissions yet.
              </div>
            ) : (
              <div className="leaderboard-list">
                <div className={"leaderboard-row leaderboard-header"}>
                  <span>rank</span>
                  <span>student</span>
                  <span>Cost</span>
                  <span>Error</span>
                </div>

                {leaderboard.map((entry) => (
                  <div key={`${entry.rank}-${entry.username}`}>
                    <div
                      className={
                        leaderboardChallenge?.archived
                          ? "leaderboard-row clickable-leaderboard-row"
                          : "leaderboard-row"
                      }
                      onClick={
                        leaderboardChallenge?.archived
                          ? () =>
                              setSelectedEquationRanks((ranks) =>
                                ranks.includes(entry.rank)
                                  ? ranks.filter((rank) => rank !== entry.rank)
                                  : [...ranks, entry.rank],
                              )
                          : undefined
                      }
                      onKeyDown={
                        leaderboardChallenge?.archived
                          ? (event) => {
                              if (event.key === "Enter" || event.key === " ") {
                                event.preventDefault();
                                setSelectedEquationRanks((ranks) =>
                                  ranks.includes(entry.rank)
                                    ? ranks.filter(
                                        (rank) => rank !== entry.rank,
                                      )
                                    : [...ranks, entry.rank],
                                );
                              }
                            }
                          : undefined
                      }
                      role={
                        leaderboardChallenge?.archived ? "button" : undefined
                      }
                      tabIndex={leaderboardChallenge?.archived ? 0 : undefined}
                      aria-pressed={
                        leaderboardChallenge?.archived
                          ? selectedEquationRanks.includes(entry.rank)
                          : undefined
                      }
                      aria-label={
                        leaderboardChallenge?.archived
                          ? `Click to compare approximation for rank ${entry.rank}`
                          : undefined
                      }
                    >
                      <span className="rank-number">{entry.rank}.</span>

                      <span className="leaderboard-user">
                        {entry.avatar_url && (
                          <img src={entry.avatar_url} alt="" />
                        )}

                        {entry.username}
                      </span>

                      <span className="numeric-cell">{entry.cost}</span>

                      <span className="numeric-cell error-cell">
                        {entry.error.toFixed(6)}
                      </span>
                      {leaderboardChallenge?.archived &&
                        selectedEquationRanks.includes(entry.rank) && (
                          <div className="selected-user-box">
                            <span>approximation used</span>
                            <div className="selected-user-equation">
                              <code>{entry.equation ?? "Unavailable"}</code>
                              <button
                                type="button"
                                className="equation-copy-icon"
                                aria-label="Copy approximation"
                                title="Copy approximation"
                                disabled={!entry.equation}
                                onClick={(event) => {
                                  event.stopPropagation();
                                  if (entry.equation) {
                                    copyEquation(
                                      "approximation",
                                      entry.equation,
                                    );
                                  }
                                }}
                              >
                                {copiedFormat === "approximation" ? "✓" : "⧉"}
                              </button>
                            </div>
                          </div>
                        )}
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="leaderboard-footnote">
              {leaderboardChallenge?.archived
                ? "Click rows to compare approximations."
                : "Ordered by cost, then error."}
            </div>

            {leaderboardTotal > 100 && (
              <div className="leaderboard-pagination">
                <button
                  type="button"
                  className="text-button"
                  disabled={leaderboardOffset === 0}
                  onClick={() =>
                    loadLeaderboard(
                      leaderboardDate ?? challenge.date,
                      Math.max(0, leaderboardOffset - 100),
                    )
                  }
                >
                  Previous
                </button>
                <span>
                  {leaderboardOffset + 1}–
                  {Math.min(
                    leaderboardOffset + leaderboard.length,
                    leaderboardTotal,
                  )}{" "}
                  of {leaderboardTotal}
                </span>
                <button
                  type="button"
                  className="text-button"
                  disabled={leaderboardOffset + 100 >= leaderboardTotal}
                  onClick={() =>
                    loadLeaderboard(
                      leaderboardDate ?? challenge.date,
                      leaderboardOffset + 100,
                    )
                  }
                >
                  Next
                </button>
              </div>
            )}
          </section>
        </div>
      )}

      {loginPromptOpen && (
        <div
          className="login-backdrop"
          onMouseDown={() => setLoginPromptOpen(false)}
        >
          <section
            className="login-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="login-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <button
              type="button"
              className="paper-close"
              aria-label="Close"
              onClick={() => setLoginPromptOpen(false)}
            >
              ×
            </button>

            <div className="modal-label">Submission note</div>

            <h2 id="login-title">Sign in to record your result</h2>

            <p>
              You can experiment anonymously, but a Google account is required
              to save a score to the daily leaderboard.
            </p>

            <a className="google-login-button" href={`${API}/auth/google`}>
              Sign in with Google
            </a>

            <button
              type="button"
              className="text-button"
              onClick={() => setLoginPromptOpen(false)}
            >
              Keep editing
            </button>
          </section>
        </div>
      )}
    </main>
  );
}
