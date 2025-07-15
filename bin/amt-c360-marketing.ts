#!/usr/bin/env node
import * as cdk from 'aws-cdk-lib';
import { AmtC360MarketingStack } from '../lib/amt-c360-marketing-stack';
import { WafStack } from '../lib/waf-stack';
const app = new cdk.App();

const wafStack = new WafStack(app, 'WafStack', {
  env: {
    region: 'us-east-1'
  },
  crossRegionReferences: true
});

new AmtC360MarketingStack(app, 'AmtC360MarketingStack', {
  webAclArn: wafStack.webAclArn,
  allowOrigin: '*',
  crossRegionReferences: true,
  env: { region: process.env.CDK_DEFAULT_REGION }
});
