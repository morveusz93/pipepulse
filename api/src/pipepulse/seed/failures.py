"""Catalog of realistic job failures for demo data.

Logs mimic GitLab runner traces: ANSI colors, `section_start`/`section_end` markers and the
runner's closing `ERROR: Job failed` line, so the log viewer is exercised on real-looking input.
"""

from dataclasses import dataclass

RED = "\x1b[31;1m"
GREEN = "\x1b[32;1m"
YELLOW = "\x1b[33;1m"
CYAN = "\x1b[36;1m"
DIM = "\x1b[0;90m"
RESET = "\x1b[0;m"
CLEAR = "\x1b[0K"


@dataclass(frozen=True)
class Failure:
    job: str
    stage: str
    reason: str
    log: str


def _trace(script: str, body: str, *, exit_code: int = 1) -> str:
    return (
        f"{CLEAR}{CYAN}Running with gitlab-runner 17.5.2 (c6eae8d7){RESET}\n"
        f"{CLEAR}  on docker-autoscaler-3 t2_kZ8sP, system ID: s_5c3e9a1f20d4\n"
        f"section_start:1729760000:prepare_executor\r{CLEAR}"
        f'{CLEAR}{CYAN}Preparing the "docker" executor{RESET}\n'
        f"section_end:1729760004:prepare_executor\r{CLEAR}"
        f"section_start:1729760004:get_sources\r{CLEAR}"
        f"{CLEAR}{CYAN}Fetching changes with git depth set to 20...{RESET}\n"
        f"section_end:1729760007:get_sources\r{CLEAR}"
        f"section_start:1729760007:step_script\r{CLEAR}"
        f'{CLEAR}{CYAN}Executing "step_script" stage of the job script{RESET}\n'
        f"{GREEN}$ {script}{RESET}\n"
        f"{body.rstrip()}\n"
        f"section_end:1729760100:step_script\r{CLEAR}"
        f"{CLEAR}{RED}ERROR: Job failed: exit code {exit_code}\n{RESET}"
    )


PYTEST_ASSERTION = Failure(
    job="test:unit",
    stage="test",
    reason="script_failure",
    log=_trace(
        "uv run pytest -q --maxfail=5",
        f"""\
........................................F.......................... [ 61%]
.........................                                          [100%]
=================================== FAILURES ===================================
{RED}______________________ test_refund_exceeds_captured_amount ______________________{RESET}

    def test_refund_exceeds_captured_amount(client, captured_payment):
        response = client.post(
            f"/payments/{{captured_payment.id}}/refunds", json={{"amount": 120_00}}
        )
>       assert response.status_code == 422
{RED}E       assert 200 == 422{RESET}
{RED}E        +  where 200 = <Response [200 OK]>.status_code{RESET}

tests/api/test_refunds.py:48: AssertionError
=========================== short test summary info ============================
{RED}FAILED tests/api/test_refunds.py::test_refund_exceeds_captured_amount - assert 200 == 422{RESET}
{RED}1 failed{RESET}, {GREEN}66 passed{RESET} in 14.27s""",
    ),
)

E2E_MISSING_MODULE = Failure(
    job="test:e2e",
    stage="test",
    reason="script_failure",
    log=_trace(
        "pnpm playwright test --reporter=line",
        f"""\
Running 42 tests using 4 workers
{DIM}[chromium] › auth/login.spec.ts:12:7 › login › redirects to dashboard{RESET}
{RED}Error: Cannot find module './auth'{RESET}
Require stack:
- /builds/acme/web-frontend/src/middleware.ts
- /builds/acme/web-frontend/.next/server/middleware.js

   at Module._resolveFilename (node:internal/modules/cjs/loader:1225:15)
   at Module._load (node:internal/modules/cjs/loader:1051:27)
   at require (node:internal/modules/cjs/helpers:110:18)
   at Object.<anonymous> (src/middleware.ts:3:1)

  {RED}1 failed{RESET}
    [chromium] › auth/login.spec.ts:12:7 › login › redirects to dashboard
  {YELLOW}3 skipped{RESET}
  {GREEN}38 passed{RESET} (1.4m)""",
    ),
)

E2E_TIMEOUT = Failure(
    job="test:e2e",
    stage="test",
    reason="script_failure",
    log=_trace(
        "pnpm playwright test --reporter=line",
        f"""\
Running 42 tests using 4 workers
{DIM}[chromium] › checkout/cart.spec.ts:58:5 › cart › applies discount code{RESET}
{RED}  1) [chromium] › checkout/cart.spec.ts:58:5 › cart › applies discount code{RESET}

    {RED}Test timeout of 30000ms exceeded.{RESET}

    Error: locator.click: Test timeout of 30000ms exceeded.
    Call log:
      - waiting for getByRole('button', {{ name: 'Apply' }})
      -   locator resolved to <button disabled class="btn btn-primary">Apply</button>
      - attempting click action
      -   waiting for element to be visible, enabled and stable
      -   element is not enabled - waiting...

      58 |   await page.getByLabel('Discount code').fill('AUTUMN24');
    > 59 |   await page.getByRole('button', {{ name: 'Apply' }}).click();
         |                                                    ^

  {RED}1 flaky{RESET}
  {GREEN}41 passed{RESET} (2.1m)""",
    ),
)

ESLINT = Failure(
    job="lint",
    stage="verify",
    reason="script_failure",
    log=_trace(
        "pnpm lint",
        f"""\
> web-frontend@2.14.0 lint /builds/acme/web-frontend
> next lint --max-warnings 0

./src/components/OrderTable.tsx
{RED}42:9  Error: React Hook useEffect has a missing dependency: 'filters'.{RESET}  react-hooks/exhaustive-deps
{RED}87:15  Error: 'formatCurrency' is defined but never used.{RESET}  @typescript-eslint/no-unused-vars

./src/lib/api.ts
{YELLOW}14:1  Warning: Unexpected console statement.{RESET}  no-console

{RED}✖ 3 problems (2 errors, 1 warning){RESET}
 ELIFECYCLE  Command failed with exit code 1.""",
    ),
)

DOCKER_BUILD = Failure(
    job="build:image",
    stage="build",
    reason="script_failure",
    log=_trace(
        "docker buildx build --push -t $CI_REGISTRY_IMAGE:$CI_COMMIT_SHORT_SHA .",
        f"""\
#9 [deps 3/4] COPY package.json pnpm-lock.yaml ./
#9 DONE 0.1s
#10 [deps 4/4] RUN pnpm install --frozen-lockfile
#10 1.204 Lockfile is up to date, resolution step is skipped
#10 1.893 {RED}ERR_PNPM_OUTDATED_LOCKFILE{RESET}  Cannot install with "frozen-lockfile" because \
pnpm-lock.yaml is not up to date with package.json
#10 1.893
#10 1.893 Note that in CI environments this setting is true by default.
#10 1.893   Failure reason:
#10 1.893   specifiers in the lockfile ({{"zod":"^3.23.8"}}) don't match specs in package.json \
({{"zod":"^3.24.1"}})
#10 {RED}ERROR: process "/bin/sh -c pnpm install --frozen-lockfile" did not complete \
successfully: exit code: 1{RESET}
------
 > [deps 4/4] RUN pnpm install --frozen-lockfile:
------
{RED}ERROR: failed to solve: process "/bin/sh -c pnpm install --frozen-lockfile" did not \
complete successfully: exit code: 1{RESET}""",
    ),
)

HELM_TIMEOUT = Failure(
    job="deploy:staging",
    stage="deploy",
    reason="script_failure",
    log=_trace(
        "helm upgrade --install api ./chart -n staging --atomic --timeout 5m",
        f"""\
Release "api" does not exist. Installing it now.
{DIM}client.go:142: [debug] creating 7 resource(s){RESET}
{DIM}wait.go:66: [debug] beginning wait for 7 resources with timeout of 5m0s{RESET}
{DIM}ready.go:303: [debug] Deployment is not ready: staging/api. 0 out of 2 expected pods \
are ready{RESET}
{DIM}ready.go:303: [debug] Deployment is not ready: staging/api. 0 out of 2 expected pods \
are ready{RESET}
{YELLOW}install.go:477: [debug] Install failed and atomic is set, uninstalling release{RESET}
{DIM}uninstall.go:102: [debug] uninstall: Deleting api{RESET}
{RED}Error: INSTALLATION FAILED: release api failed, and has been uninstalled due to atomic \
being set: context deadline exceeded{RESET}

$ kubectl -n staging get events --field-selector type=Warning | tail -3
Warning  Failed     pod/api-7c9f8d6b5-x2kqp  Error: secret "api-db-credentials" not found
Warning  Failed     pod/api-7c9f8d6b5-mw4tz  Error: secret "api-db-credentials" not found
Warning  BackOff    pod/api-7c9f8d6b5-x2kqp  Back-off restarting failed container""",
    ),
)

TERRAFORM_PLAN = Failure(
    job="plan",
    stage="plan",
    reason="script_failure",
    log=_trace(
        "terraform plan -input=false -out=plan.tfplan",
        f"""\
module.network.aws_vpc.main: Refreshing state... [id=vpc-0a1b2c3d4e5f60718]
module.eks.aws_eks_cluster.this: Refreshing state... [id=acme-prod]
module.dns.aws_route53_zone.public: Refreshing state... [id=Z03810172E7Q5WTVYTLKL]
╷
│ {RED}Error: Unsupported argument{RESET}
│
│   on modules/eks/node_groups.tf line 31, in resource "aws_eks_node_group" "general":
│   31:   instance_type = var.node_instance_type
│
│ An argument named "instance_type" is not expected here. Did you mean "instance_types"?
╵""",
    ),
)

GO_RACE = Failure(
    job="test",
    stage="test",
    reason="script_failure",
    log=_trace(
        "go test -race -count=1 ./...",
        f"""\
ok      github.com/acme/payments-worker/internal/ledger     2.418s
ok      github.com/acme/payments-worker/internal/queue      1.102s
==================
{RED}WARNING: DATA RACE{RESET}
Write at 0x00c0001a4f08 by goroutine 27:
  github.com/acme/payments-worker/internal/settle.(*Batcher).Add()
      /builds/acme/payments-worker/internal/settle/batcher.go:58 +0x1a4
Previous read at 0x00c0001a4f08 by goroutine 31:
  github.com/acme/payments-worker/internal/settle.(*Batcher).Flush()
      /builds/acme/payments-worker/internal/settle/batcher.go:74 +0x8c
==================
--- FAIL: TestBatcher_ConcurrentFlush (0.31s)
    testing.go:1398: race detected during execution of test
{RED}FAIL{RESET}
{RED}FAIL    github.com/acme/payments-worker/internal/settle     0.842s{RESET}
{RED}FAIL{RESET}""",
    ),
)

GRADLE_COMPILE = Failure(
    job="build:android",
    stage="build",
    reason="script_failure",
    log=_trace(
        "./gradlew assembleRelease --no-daemon",
        f"""\
> Task :app:kaptGenerateStubsReleaseKotlin
> Task :app:compileReleaseKotlin {RED}FAILED{RESET}
{RED}e: file:///builds/acme/mobile-app/app/src/main/java/com/acme/app/ui/OrdersScreen.kt:84:21 \
Unresolved reference: collectAsStateWithLifecycle{RESET}
{RED}e: file:///builds/acme/mobile-app/app/src/main/java/com/acme/app/ui/OrdersScreen.kt:91:13 \
Type mismatch: inferred type is List<Order>? but List<Order> was expected{RESET}

FAILURE: Build failed with an exception.

* What went wrong:
Execution failed for task ':app:compileReleaseKotlin'.
> A failure occurred while executing org.jetbrains.kotlin.compilerRunner.GradleCompilerRunnerWithWorkers$GradleKotlinCompilerWorkAction
   > Compilation error. See log for more details

{RED}BUILD FAILED{RESET} in 3m 41s
57 actionable tasks: 41 executed, 16 up-to-date""",
    ),
)

UI_TEST_FLAKY = Failure(
    job="test:ui",
    stage="test",
    reason="script_failure",
    log=_trace(
        "./gradlew connectedReleaseAndroidTest",
        f"""\
Starting 128 tests on Pixel_7_API_34(AVD) - 14

com.acme.app.CheckoutFlowTest > completesPurchaseWithSavedCard[Pixel_7_API_34(AVD) - 14] \
{RED}FAILED{RESET}
\tandroidx.test.espresso.NoMatchingViewException: No views in hierarchy found matching: \
with text: is "Pay now"
\tat dalvik.system.VMStack.getThreadStackTrace(Native Method)
\tat com.acme.app.CheckoutFlowTest.completesPurchaseWithSavedCard(CheckoutFlowTest.kt:67)

Tests on Pixel_7_API_34(AVD) - 14 failed: There was 1 failure(s).

{RED}FAILURE: Build failed with an exception.{RESET}
* What went wrong:
Execution failed for task ':app:connectedReleaseAndroidTest'.
> There were failing tests. See the report at: \
file:///builds/acme/mobile-app/app/build/reports/androidTests/connected/release/index.html""",
    ),
)

DBT_MODEL = Failure(
    job="dbt:run",
    stage="transform",
    reason="script_failure",
    log=_trace(
        "dbt run --target prod --select tag:nightly",
        f"""\
04:12:07  Running with dbt=1.8.7
04:12:09  Found 84 models, 212 data tests, 19 sources, 0 exposures, 612 macros
04:12:11  Concurrency: 8 threads (target='prod')
04:12:14  31 of 84 START sql incremental model analytics.fct_orders ........ [RUN]
04:12:41  31 of 84 {RED}ERROR creating sql incremental model analytics.fct_orders{RESET} \
[{RED}ERROR{RESET} in 27.18s]
04:13:02  Finished running 84 models in 0 hours 0 minutes and 53.12 seconds (53.12s).
04:13:02
04:13:02  {RED}Completed with 1 error and 0 warnings:{RESET}
04:13:02
04:13:02    {RED}Database Error in model fct_orders (models/marts/fct_orders.sql){RESET}
04:13:02    column "discount_amount" does not exist
04:13:02    LINE 14:     coalesce(o.discount_amount, 0) as discount_amount,
04:13:02                          ^
04:13:02    HINT:  Perhaps you meant to reference the column "o.discount_total".
04:13:02
04:13:02  Done. PASS=52 WARN=0 ERROR=1 SKIP=31 TOTAL=84""",
    ),
)

RUNNER_TIMEOUT = Failure(
    job="test:integration",
    stage="test",
    reason="stuck_or_timeout_failure",
    log=(
        f"{CLEAR}{CYAN}Running with gitlab-runner 17.5.2 (c6eae8d7){RESET}\n"
        f"{GREEN}$ ./scripts/integration-tests.sh{RESET}\n"
        "Waiting for postgres at postgres:5432...\n"
        "Waiting for postgres at postgres:5432...\n"
        "Waiting for postgres at postgres:5432...\n"
        f"{RED}ERROR: Job failed: execution took longer than 1h0m0s seconds\n{RESET}"
    ),
)

RUNNER_SYSTEM = Failure(
    job="build:image",
    stage="build",
    reason="runner_system_failure",
    log=(
        f"{CLEAR}{CYAN}Running with gitlab-runner 17.5.2 (c6eae8d7){RESET}\n"
        f'{CLEAR}{CYAN}Preparing the "docker" executor{RESET}\n'
        f'{YELLOW}WARNING: Failed to pull image with policy "always": '
        "toomanyrequests: You have reached your pull rate limit.\n"
        f"{RESET}{RED}ERROR: Job failed (system failure): failed to pull image "
        '"docker:27-dind" with specified policies [always]\n'
        f"{RESET}"
    ),
)
