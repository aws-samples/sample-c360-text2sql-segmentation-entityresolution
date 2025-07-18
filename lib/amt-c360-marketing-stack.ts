import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import { DataStorage } from './data-storage';
import { EntityResolutionService } from './entity-resolution-service';
import { DataIntegrationWorkflow } from './data-integration-workflow';
import { PersonalizeService } from './personalize';
import { WebBackend } from './webbackend';
import { Frontend } from './frontend';
import { PersonalizeStore } from './solution-version-store';
import { PersonalizeSegmentWorkflow } from './personalize-segment-workflow';

export interface AmtC360MarketingStackProps extends cdk.StackProps {
  webAclArn: string;
  allowOrigin: string;
  entityResolutionEnabled: boolean;
  personalizeEnabled: boolean;
}

export class AmtC360MarketingStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: AmtC360MarketingStackProps) {
    super(scope, id, props);

    // Create data storage layer
    const dataStorage = new DataStorage(this, 'DataStorage', {
      entityResolutionEnabled: props.entityResolutionEnabled,
      personalizeEnabled: props.personalizeEnabled
    });

    // Create Entity Resolution

    const entityResolutionService = props.entityResolutionEnabled
      ? new EntityResolutionService(this, 'EntityResolution', {
          dataStorage
        })
      : undefined;

    // Create Personalize service
    const personalizeService = props.personalizeEnabled
      ? new PersonalizeService(this, 'PersonalizeService', {
          dataStorage
        })
      : undefined;

    // Create personalize store
    const personalizeStore = props.personalizeEnabled ? new PersonalizeStore(this, 'PersonalizeStore', {}) : undefined;

    // Create data integration workflow execution layer
    new DataIntegrationWorkflow(this, 'DataIntegrationWorkflow', {
      entityResolutionService,
      dataStorage,
      personalizeService,
      personalizeStore
    });

    // Create personalize segment workflow

    const personalizeSegmentWorkflow =
      personalizeService && personalizeStore
        ? new PersonalizeSegmentWorkflow(this, 'PersonalizeSegmentWorkflow', {
            dataStorage,
            personalizeService,
            personalizeStore
          })
        : undefined;

    // Create Web backend layer
    const webBackend = new WebBackend(this, 'WebBackend', {
      dataStorage: dataStorage,
      personalizeSegmentWorkflow: personalizeSegmentWorkflow,
      personalizeStore: personalizeStore,
      allowOrigin: props.allowOrigin
    });

    new Frontend(this, 'Frontend', {
      backend: webBackend,
      webAclArn: props.webAclArn
    });
  }
}
