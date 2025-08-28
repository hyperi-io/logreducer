# Claude Code End-of-Day Sequence

## Copy & Paste This Into Any Claude Session

```
Please perform the end-of-day sequence:

1. **Summarize Today's Work**
   - List key accomplishments
   - Note any unfinished tasks
   - Document important decisions made

2. **Update CLAUDE.md**
   - Add today's work to the development log
   - Update any changed configurations or decisions
   - Note any warnings for future sessions

3. **Check Git Status**
   - Run: git status
   - List any uncommitted changes
   - Note which files should NOT be committed (like claude-sync)

4. **Sync Claude State** (if claude-sync exists)
   - Run: /usr/bin/python3 scripts/claude-sync --message "eod: End of day sync - [brief description]"
   - Confirm sync successful
   - Note: This is standalone, doesn't affect project git

5. **Create Session Handover Notes**
   - Current state of the project
   - Next steps to tackle
   - Any blockers or issues
   - Environment state (venv, dependencies, etc.)

6. **Final Checks**
   - Ensure no sensitive data in logs
   - Verify CI/CD still works if changes were made
   - Check that .gitignore still excludes Claude files

Please provide the output in a format I can save for the next session.
```

## Standard End-of-Day Report Template

When Claude executes the above, it should produce something like:

```markdown
# End of Day Report - [DATE]

## Today's Accomplishments
- ✅ [Task 1 completed]
- ✅ [Task 2 completed]
- 🔄 [Task 3 in progress]
- ⏸️ [Task 4 not started]

## Key Decisions/Changes
- [Important decision 1]
- [Configuration change 2]
- [Architecture decision 3]

## Git Status
**Modified files (to commit):**
- file1.py - [reason for change]
- file2.md - [reason for change]

**Files to exclude from commit:**
- CLAUDE.md - Claude documentation
- scripts/claude-sync - Standalone utility
- .claude/ - Claude settings

## Claude State Sync
✅ Successfully synced to https://github.com/[user]/claude-state/[project]/
- Sync message: "eod: [description]"
- Files synced: 9 items
- No interference with project git confirmed

## Handover Notes for Next Session

### Current State
- Project version: X.X.X
- Branch: main
- Tests: ✅ All passing
- Build: ✅ Successful
- CI/CD: ✅ Functional

### Next Steps
1. [Priority task 1]
2. [Priority task 2]
3. [Priority task 3]

### Blockers/Issues
- [Any blocking issues]
- [Dependencies needed]
- [Questions for user]

### Environment Notes
- Python: 3.12
- Virtual env: .venv (active)
- Key dependencies: [list any added today]

## Important Reminders for Next Session
- ⚠️ [Warning 1]
- ⚠️ [Warning 2]
- 📝 [Note 1]

## Session Metadata
- Session duration: [X hours]
- Lines of code changed: ~[X]
- Files modified: [X]
- Tests added/modified: [X]
```

## Quick Commands Reference

For easy copy-paste during end-of-day:

```bash
# Check git status
git status --short

# Check what would be synced (dry run)
/usr/bin/python3 scripts/claude-sync --dry-run

# Perform actual sync
/usr/bin/python3 scripts/claude-sync --message "eod: Summary of today's work"

# Verify tests still pass
scripts/pdev test-unit

# Check version consistency
scripts/pdev version-check

# See recent commits
git log --oneline -5
```

## Customization Notes

You can customize this sequence for different projects by:

1. **Project-Specific Checks**: Add project-specific validation
2. **Different Sync Repos**: Adjust the claude-sync repo URL
3. **Team Handovers**: Add team-specific notes if sharing
4. **Time Zones**: Include timezone in timestamps
5. **Metrics**: Add productivity metrics if desired

## Usage Instructions

1. **At End of Session**: Copy the first code block and paste into Claude
2. **Save the Report**: Copy Claude's response to a file or notes
3. **Next Session Start**: Reference the saved report to continue work
4. **Weekly Reviews**: Collect daily reports for weekly summaries

## Example End-of-Day Message

```
Please perform the end-of-day sequence:

1. Summarize today's work on the LogReducer project
2. Update CLAUDE.md with today's accomplishments  
3. Check git status and list uncommitted changes
4. Run claude-sync to backup Claude state
5. Create handover notes for tomorrow's session
6. Verify CI/CD and tests are still working

Today we worked on making claude-sync completely standalone and tested the CI/CD pipeline.
```

## Benefits

- **Consistency**: Same process across all projects
- **Continuity**: Smooth handover between sessions
- **Safety**: Ensures Claude files don't interfere with project
- **Documentation**: Builds a development history
- **Recovery**: Can restore context if session is lost

---

*This template is designed to work across any project. Keep it in your notes for quick access at the end of each Claude Code session.*