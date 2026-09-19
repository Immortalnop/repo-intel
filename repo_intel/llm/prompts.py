"""Prompt templates for the optional LLM narrative."""

BRIEFING_PROMPT = (
    "You are a software engineering analyst. Using ONLY the metrics below, "
    "write a concise repository health briefing (max ~180 words) for an "
    "engineering lead. Cover: overall health, top bug-prone modules, "
    "knowledge/bus-factor risk, and a release recommendation. Be specific, "
    "no fluff, no invented facts.\n\n"
    "Health score: {health}/100\n"
    "Commits: {commits}, Files: {files}, Authors: {authors}, "
    "Bug-fix commits: {bugfix}\n"
    "Release readiness: {readiness}\n"
    "Top hotspots: {hotspots}\n"
    "Knowledge silos: {silos}\n"
    "Flags: {flags}\n"
)
