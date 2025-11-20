from aws_cdk import (
    aws_events as events,
    aws_events_targets as targets,
    aws_stepfunctions as sfn,
)
from constructs import Construct
import datetime


class EventBridgeScheduler(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        environment: str,
        state_machine_arn: str,
        **kwargs
    ):
        super().__init__(scope, construct_id, **kwargs)

        ENV = environment

        # Import state machine from ARN
        state_machine = sfn.StateMachine.from_state_machine_arn(
            self, 'StateMachine',
            state_machine_arn=state_machine_arn
        )

        # Weekly schedule: Sundays at 2:00 AM UTC
        rule = events.Rule(
            self, 'WeeklySchedule',
            rule_name=f'nih-reporter-weekly-{ENV}',
            schedule=events.Schedule.cron(
                minute='0',
                hour='2',
                week_day='SUN'
            ),
            description='Weekly NIH Reporter pipeline trigger on Sundays at 2:00 AM UTC'
        )

        # Default: last 2 fiscal years
        current_year = datetime.datetime.now().year
        fiscal_years = [current_year, current_year - 1]

        # Add state machine as target
        rule.add_target(
            targets.SfnStateMachine(
                state_machine,
                input=events.RuleTargetInput.from_object({
                    'fiscal_years': fiscal_years,
                    'fiscal_years_str': ','.join(map(str, fiscal_years))
                })
            )
        )

        self.rule_name = rule.rule_name

