module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // Type must be one of the following
    'type-enum': [
      2,
      'always',
      [
        'feat',     // New feature (minor version bump)
        'fix',      // Bug fix (patch version bump)
        'docs',     // Documentation only changes
        'style',    // Code style changes (formatting, missing semi-colons, etc)
        'refactor', // Code refactoring without adding features or fixing bugs
        'perf',     // Performance improvements (patch version bump)
        'test',     // Adding missing tests or correcting existing tests
        'build',    // Changes to build process or dependencies
        'ci',       // Changes to CI configuration files and scripts
        'chore',    // Other changes that don't modify src or test files
        'revert'    // Reverts a previous commit
      ]
    ],
    // Scope is optional but when provided, should be lowercase
    'scope-case': [2, 'always', 'lower-case'],
    // Subject must not be empty
    'subject-empty': [2, 'never'],
    // Subject must not end with period
    'subject-full-stop': [2, 'never', '.'],
    // Subject must be in lowercase
    'subject-case': [2, 'always', 'lower-case'],
    // Body should have blank line before it
    'body-leading-blank': [2, 'always'],
    // Footer should have blank line before it
    'footer-leading-blank': [2, 'always'],
    // Max length of header (type(scope): subject)
    'header-max-length': [2, 'always', 100],
    // Warn about max line length in body (can be longer for URLs, etc)
    'body-max-line-length': [1, 'always', 100],
    // Footer can be longer (for BREAKING CHANGE descriptions)
    'footer-max-line-length': [1, 'always', 100]
  },
  // Helper to print all allowed types
  helpUrl: 'https://www.conventionalcommits.org/',
  // Custom prompt messages
  prompt: {
    settings: {},
    messages: {
      skip: ':skip',
      max: 'upper %d chars',
      min: '%d chars at least',
      emptyWarning: 'can not be empty',
      upperLimitWarning: 'over limit',
      lowerLimitWarning: 'below limit'
    },
    questions: {
      type: {
        description: "Select type (determines version bump)",
        enum: {
          feat: {
            description: 'New feature (triggers minor version bump)',
            title: 'Features'
          },
          fix: {
            description: 'Bug fix (triggers patch version bump)',
            title: 'Bug Fixes'
          },
          docs: {
            description: 'Documentation changes only',
            title: 'Documentation'
          },
          style: {
            description: 'Code style changes (formatting, missing semi-colons, etc)',
            title: 'Styles'
          },
          refactor: {
            description: 'Code refactoring without feature or bug fix',
            title: 'Code Refactoring'
          },
          perf: {
            description: 'Performance improvements (triggers patch version bump)',
            title: 'Performance'
          },
          test: {
            description: 'Adding or updating tests',
            title: 'Tests'
          },
          build: {
            description: 'Build system or dependency changes',
            title: 'Builds'
          },
          ci: {
            description: 'CI configuration changes',
            title: 'CI'
          },
          chore: {
            description: 'Other changes that don\'t affect source or test files',
            title: 'Chores'
          },
          revert: {
            description: 'Revert a previous commit',
            title: 'Reverts'
          }
        }
      },
      scope: {
        description: 'What is the scope of this change (optional)'
      },
      subject: {
        description: 'Write a short description (imperative mood, lowercase)'
      },
      body: {
        description: 'Provide a longer description (optional)'
      },
      breaking: {
        description: 'List any BREAKING CHANGES (triggers major version bump)'
      },
      issues: {
        description: 'Reference any JIRA issues (e.g., "PROJ-123, PROJ-456")'
      }
    }
  }
};