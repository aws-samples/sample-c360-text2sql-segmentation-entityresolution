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
}

export class AmtC360MarketingStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: AmtC360MarketingStackProps) {
    super(scope, id, props);

    // Create data storage layer
    const dataStorage = new DataStorage(this, 'DataStorage', {});

    // Create Entity Resolution
    const entityResolutionService = new EntityResolutionService(this, 'EntityResolution', {
      dataStorage
    });

    // Create Personalize service
    const personalizeService = new PersonalizeService(this, 'PersonalizeService', {
      dataStorage
    });

    // Create personalize store
    const personalizeStore = new PersonalizeStore(this, 'PersonalizeStore', {});

    // Create data integration workflow execution layer
    new DataIntegrationWorkflow(this, 'DataIntegrationWorkflow', {
      entityResolutionService,
      dataStorage,
      personalizeService,
      personalizeStore
    });

    // Create personalize segment workflow
    const personalizeSegmentWorkflow = new PersonalizeSegmentWorkflow(this, 'PersonalizeSegmentWorkflow', {
      dataStorage,
      personalizeService,
      personalizeStore
    });

    // Create Web backend layer
    const webBackend = new WebBackend(this, 'WebBackend', {
      dataStorage: dataStorage,
      personalizeSegmentWorkflow: personalizeSegmentWorkflow,
      personalizeStore: personalizeStore
    });

    new Frontend(this, 'Frontend', {
      backend: webBackend,
      webAclArn: props.webAclArn
    });
  }
}
