#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { AmtC360MarketingStack } from '../lib/amt-c360-marketing-stack';
import { WafStack } from '../lib/waf-stack';
const app = new cdk.App();

const allowOrigin = app.node.tryGetContext('corsAllowOrigin');
const personalizeEnabled = app.node.tryGetContext('personalizeEnabled');
const entityResolutionEnabled = app.node.tryGetContext('entityResolutionEnabled');
const stackPrefix = app.node.tryGetContext('stackPrefix') || '';

if (personalizeEnabled && !entityResolutionEnabled) {
  throw new Error(
    'personalizeEnabled cannot be true when entityResolutionEnabled is false. The sample implementation of Personalize depends on Entity Resolution. please customize lambda/create_personalize_dataset_import_job SQL in order to achieve that.'
  );
}

const marketingStackName = stackPrefix ? `${stackPrefix}_AmtC360MarketingStack` : 'AmtC360MarketingStack';
const wafStackName = stackPrefix ? `${stackPrefix}_AmtC360WafStack` : 'AmtC360WafStack';

const wafStack = new WafStack(app, wafStackName, {
  env: {
    region: 'us-east-1'
  },
  crossRegionReferences: true
});

new AmtC360MarketingStack(app, marketingStackName, {
  webAclArn: wafStack.webAclArn,
  allowOrigin: allowOrigin,
  personalizeEnabled: personalizeEnabled,
  entityResolutionEnabled: entityResolutionEnabled,
  crossRegionReferences: true,
  env: { region: process.env.CDK_DEFAULT_REGION }
});
