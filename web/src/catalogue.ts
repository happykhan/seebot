import { analyzerRuleMetadata } from './ruleMetadata'

export interface MetricDefinition {
  label: string
  shortLabel: string
  unit: string
  explanation: string
  direction: 'higher' | 'lower' | 'neutral'
}

export const metricDefinitions: Record<string, MetricDefinition> = {
  days_since_last_commit: {
    label: 'Days since last non-bot commit', shortLabel: 'Last non-bot commit', unit: 'days', direction: 'lower',
    explanation: 'Elapsed days between the review date and the latest commit not attributed to an automated account.',
  },
  commits_last_12_months: {
    label: 'Commits in the previous 12 months', shortLabel: 'Commits in 12 months', unit: 'commits', direction: 'higher',
    explanation: 'Number of non-bot commits during the 12 months ending on the review date.',
  },
  active_months_last_12_months: {
    label: 'Active months in the previous 12 months', shortLabel: 'Active months', unit: 'months', direction: 'higher',
    explanation: 'Number of calendar months containing at least one non-bot commit during the previous 12 months.',
  },
  days_since_latest_release: {
    label: 'Days since latest release', shortLabel: 'Latest release', unit: 'days', direction: 'lower',
    explanation: 'Elapsed days between the review date and the latest published GitHub release.',
  },
  production_lines: {
    label: 'Production source lines', shortLabel: 'Source lines', unit: 'lines', direction: 'neutral',
    explanation: 'Physical lines in the production source files selected for the software and language.',
  },
  maximum_file_lines: {
    label: 'Longest production source file', shortLabel: 'Longest source file', unit: 'lines', direction: 'lower',
    explanation: 'Physical line count of the longest production source file. Large files can indicate concentrated responsibilities.',
  },
  percent_files_over_500: {
    label: 'Production files over 500 lines', shortLabel: 'Files over 500 lines', unit: '%', direction: 'lower',
    explanation: 'Percentage of production source files containing more than 500 physical lines.',
  },
  function_length_p90: {
    label: '90th percentile function length', shortLabel: 'Function length p90', unit: 'lines', direction: 'lower',
    explanation: 'Ninety percent of detected functions are this length or shorter. This describes the longer end of the function-size distribution.',
  },
  complexity_p90: {
    label: '90th percentile cyclomatic complexity', shortLabel: 'Complexity p90', unit: '', direction: 'lower',
    explanation: 'Ninety percent of detected functions have this cyclomatic complexity or lower. Complexity counts independent control-flow paths.',
  },
  duplication_percent: {
    label: 'Repeated source blocks', shortLabel: 'Repeated source blocks', unit: '%', direction: 'lower',
    explanation: 'Percentage of normalized production lines occurring in repeated exact six-line blocks. It is a simple duplication indicator, not a clone analysis.',
  },
  documentation_coverage: {
    label: 'Documented functions', shortLabel: 'Documented functions', unit: '%', direction: 'higher',
    explanation: 'Share of detected functions associated with a language-appropriate docstring or documentation comment.',
  },
  dead_code_candidates: {
    label: 'Dead-code candidates', shortLabel: 'Dead-code candidates', unit: 'candidates', direction: 'lower',
    explanation: 'Potentially unused code reported by the configured analyzer. Candidates require manual review before removal.',
  },
  lint_findings_per_kloc: {
    label: 'Static-analysis findings per 1,000 lines', shortLabel: 'Static-analysis findings', unit: 'per kLOC', direction: 'lower',
    explanation: 'Language-specific linter findings divided by production source size. Rule sets differ between languages.',
  },
  security_findings_per_kloc: {
    label: 'Security findings per 1,000 lines', shortLabel: 'Security findings', unit: 'per kLOC', direction: 'lower',
    explanation: 'Language-specific security-analyzer findings divided by production source size.',
  },
  dependency_advisories: {
    label: 'Known dependency vulnerabilities', shortLabel: 'Dependency vulnerabilities', unit: 'advisories', direction: 'lower',
    explanation: 'Known advisories returned for exact packages in the audited installation or supported dependency lockfiles and manifests.',
  },
}

export const historyDefinitions = {
  physical_lines: { metricKey: 'production_lines', ...metricDefinitions.production_lines },
  maximum_file: { metricKey: 'maximum_file_lines', ...metricDefinitions.maximum_file_lines },
  complexity_p90: { metricKey: 'complexity_p90', ...metricDefinitions.complexity_p90 },
  documentation: { metricKey: 'documentation_coverage', ...metricDefinitions.documentation_coverage },
  duplication: { metricKey: 'duplication_percent', ...metricDefinitions.duplication_percent },
}

export type HistoryMetric = keyof typeof historyDefinitions

export const contractCatalogue: Record<string, { label: string, explanation: string, expectation: string }> = {
  'CLI-HELP-001': {
    label: 'Help message',
    explanation: 'Runs the documented help option and checks that useful guidance is returned.',
    expectation: 'Exit successfully and display non-empty help text.',
  },
  'CLI-VERSION-001': {
    label: 'Version reporting',
    explanation: 'Runs the documented version option and checks for the audited software version.',
    expectation: 'Exit successfully and identify the installed version.',
  },
  'CLI-NOARGS-001': {
    label: 'No arguments',
    explanation: 'Starts the command without arguments to see whether it explains what input is required.',
    expectation: 'Show useful guidance or a clear error without an internal crash.',
  },
  'CLI-VALID-RUN-001': {
    label: 'Small example run',
    explanation: 'Runs a short, reviewed example using representative biological data.',
    expectation: 'Complete within the time limit and produce output with the expected structure.',
  },
  'CLI-STREAMS-001': {
    label: 'Standard input and output',
    explanation: 'Checks whether the reviewed interface can participate in a command-line pipeline.',
    expectation: 'Read standard input or write standard output as documented, with structurally valid output.',
  },
  'CLI-MISSING-INPUT-001': {
    label: 'Missing input',
    explanation: 'Supplies a path that does not exist.',
    expectation: 'Return a non-zero exit code and a useful diagnostic without an internal crash.',
  },
  'CLI-EMPTY-INPUT-001': {
    label: 'Zero-byte input',
    explanation: 'Supplies an empty file where biological data are expected.',
    expectation: 'Reject unusable input clearly without an internal crash or inappropriate output.',
  },
  'CLI-SEMANTICALLY-EMPTY-INPUT-001': {
    label: 'Valid input with no records',
    explanation: 'Supplies a valid file or stream containing headers where required but no biological records.',
    expectation: 'Complete without an internal crash and produce structurally valid output representing zero records.',
  },
  'CLI-MALFORMED-INPUT-001': {
    label: 'Malformed input',
    explanation: 'Supplies a deliberately truncated or syntactically damaged file in the expected format.',
    expectation: 'Reject malformed data with a non-zero exit code and a useful diagnostic.',
  },
  'CLI-WRONG-FORMAT-001': {
    label: 'Wrong biological format',
    explanation: 'Supplies a valid biological file of the wrong type.',
    expectation: 'Identify or reject the incompatible input without an internal crash.',
  },
  'CLI-INVALID-OPTION-001': {
    label: 'Unrecognized option',
    explanation: 'Supplies an option that the command does not implement.',
    expectation: 'Return a non-zero exit code and identify the invalid option.',
  },
  'CLI-INVALID-VALUE-001': {
    label: 'Invalid parameter value',
    explanation: 'Supplies an out-of-range or otherwise invalid value to a reviewed option.',
    expectation: 'Reject the value and explain the accepted range or form.',
  },
  'CLI-UNWRITABLE-OUTPUT-001': {
    label: 'Unwritable output',
    explanation: 'Directs output to a location that cannot be written.',
    expectation: 'Return a non-zero exit code and identify the output problem without leaving misleading files.',
  },
}

export const practiceDescriptions: Record<string, string> = {
  README: 'A README provides the first description and entry point for users.',
  'Installation instructions': 'The repository explains how to install the software.',
  'Usage example': 'A concrete command or worked example demonstrates typical use.',
  Licence: 'A licence states how the software may be used and redistributed.',
  'Citation information': 'The repository tells users how to cite the software.',
  'Recognized standard tests': 'Conventional test files or test-framework configuration are present.',
  'Verification CI': 'Continuous integration is configured to run verification checks.',
}

const ruleDescriptions: Record<string, string> = {
  'cppcheck:nullPointerOutOfMemory': 'A pointer may be used after an allocation without first checking whether allocation failed.',
  'cppcheck:unusedStructMember': 'A member of a structure appears not to be read or written.',
  'cppcheck:constVariablePointer': 'A pointer variable could be declared const because the pointer itself is not reassigned.',
  'cppcheck:constParameterPointer': 'A pointer parameter could be made const because the function does not modify the pointed-to value.',
  'cppcheck:shadowVariable': 'A local declaration hides another variable with the same name.',
  'cppcheck:variableScope': 'A variable is declared in a wider scope than its observed use requires.',
  'cppcheck:unreadVariable': 'A value is assigned to a variable but is not subsequently read.',
  'cppcheck:invalidPrintfArgType_sint': 'A printf-style format specifier does not match the supplied signed-integer argument type.',
  'cppcheck:passedByValue': 'A potentially expensive object is passed by value where a reference may avoid a copy.',
  'cppcheck:clarifyCalculation': 'An expression would be clearer with explicit parentheses or simpler calculation structure.',
  'cppcheck:constParameterCallback': 'A callback parameter could use const qualification because the value is not modified.',
  'cppcheck:knownConditionTrueFalse': 'A condition can be determined as always true or always false from the surrounding code.',
  'cppcheck:postfixOperator': 'A postfix increment or decrement may create an unnecessary temporary value.',
  'cppcheck:arrayIndexThenCheck': 'An array element may be accessed before the index is checked.',
  'cppcheck:missingOverride': 'A C++ method overrides a base-class method but is not marked override.',
  'cppcheck:unknownMacro': 'Analysis encountered a macro whose definition was unavailable, which can reduce result reliability.',
  'cython-lint:E501': 'A line exceeds the configured maximum length.',
  'cython-lint:E221': 'Multiple spaces appear before an operator.',
  'cython-lint:E228': 'Whitespace is missing around a modulo operator.',
  'cython-lint:E222': 'Multiple spaces appear after an operator.',
  'cython-lint:W291': 'A line contains trailing whitespace.',
  'cython-lint:E701': 'Multiple statements appear on one line after a colon.',
  'cython-lint:E703': 'A statement ends with an unnecessary semicolon.',
  'cython-lint:E111': 'Indentation is not a multiple of the configured indentation width.',
  'ruff:UP006': 'A collection type annotation uses an older typing form rather than the built-in generic form.',
  'ruff:UP045': 'An Optional annotation can use the modern X | None syntax.',
  'ruff:UP035': 'An import comes from a deprecated location and has a newer replacement.',
  'pylint:missing-function-docstring': 'A function or method has no docstring.',
  'pylint:missing-class-docstring': 'A class has no docstring.',
  'pylint:no-else-return': 'An else block follows a branch that already returns and can usually be simplified.',
  'bandit:B101': 'An assert statement is used; assertions can be removed when Python runs with optimization.',
  'bandit:B102': 'The built-in exec function is used to execute dynamically supplied Python code, which can be dangerous when input is not fully controlled.',
  'PMD:SystemPrintln': 'Java code writes directly through System.out or System.err instead of a logging abstraction.',
  'PMD:AvoidLiteralsInIfCondition': 'A conditional compares against a literal value that may be clearer as a named constant.',
  'PMD:AssignmentInOperand': 'An assignment occurs inside another expression, which can be difficult to read or accidental.',
  'Perl::Critic:RegularExpressions::RequireDotMatchAnything': 'A regular expression should state explicitly whether a dot may match newline characters.',
  'Perl::Critic:RegularExpressions::RequireExtendedFormatting': 'A complex regular expression should use extended formatting for readability.',
  'Perl::Critic:RegularExpressions::RequireLineBoundaryMatching': 'A regular expression should state explicitly how line boundaries are handled.',
}

export function describeRule(analyzer: string, rule: string): string {
  const generated = analyzerRuleMetadata[`${analyzer}:${rule}`]
  if (generated) return generated.description
  const known = ruleDescriptions[`${analyzer}:${rule}`]
  if (known) return known
  const words = rule.replaceAll('::', ' ').replaceAll(/([a-z])([A-Z])/g, '$1 $2').replaceAll(/[-_]/g, ' ').trim()
  return `${words || rule} is a finding reported by ${analyzer}. Follow the analyzer documentation link for the rule's exact condition and suggested response.`
}

export function ruleDocumentationUrl(analyzer: string, rule: string): string | null {
  const generated = analyzerRuleMetadata[`${analyzer}:${rule}`]
  if (generated) return generated.url
  if (analyzer === 'bandit' && rule === 'B101') return 'https://bandit.readthedocs.io/en/latest/plugins/b101_assert_used.html'
  if (analyzer === 'bandit' && rule === 'B102') return 'https://bandit.readthedocs.io/en/latest/plugins/b102_exec_used.html'
  if (analyzer === 'bandit') return 'https://bandit.readthedocs.io/en/latest/plugins/index.html'
  if (analyzer === 'ruff') return 'https://docs.astral.sh/ruff/rules/'
  if (analyzer === 'pylint') return `https://pylint.readthedocs.io/en/latest/user_guide/messages/${rule[0] ?? 'c'}/${rule}.html`
  if (analyzer === 'cppcheck') return 'https://cppcheck.sourceforge.io/manual.html'
  if (analyzer === 'PMD') return 'https://docs.pmd-code.org/latest/pmd_rules_java.html'
  if (analyzer === 'cython-lint') return 'https://github.com/MarcoGorelli/cython-lint'
  if (analyzer === 'Perl::Critic') return 'https://metacpan.org/pod/Perl::Critic'
  return null
}

export function severityClass(severity: string | null | undefined): string {
  const value = (severity ?? 'unspecified').toLowerCase()
  if (['critical', 'high', 'error', '1', '2'].some((token) => value === token)) return 'severity-high'
  if (['warning', 'medium', '3'].some((token) => value === token)) return 'severity-medium'
  if (['low', 'style', 'performance', 'portability', 'convention', 'refactor', '4', '5'].some((token) => value === token)) return 'severity-low'
  return 'severity-unspecified'
}
