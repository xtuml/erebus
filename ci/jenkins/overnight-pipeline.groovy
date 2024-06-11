import groovy.json.JsonSlurper
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

pipeline {
    agent any
    stages {
        // this requires the 'htmlpublisher'  plugin
        stage("TH-main-runtime"){
            steps {
                script {
                    env.DATA_HOME         = "$JENKINS_HOME/../data-scripts/jenkins_test_cases"
                    env.OUTPUTS           = "$JENKINS_HOME/workspace/overnight-pipeline"
                    env.PV_BOX            = "172.16.0.21"
                    env.TH_BOX            = "172.16.0.16:8800"
                    env.PV_DEPLOY_PATH    = "/home/itoperations/munin_1.3.1-midstage3/deploy"
                    env.WAIT_INTERVAL     = "10"
                    env.CONFIG_FILE_NAME  = "test_config.yaml"

                    // getting around scoping issues
                    addInfo = ""

                    externalFunctions = load("$JENKINS_HOME/groovy-scripts/pipeline-functions.groovy")

                    TEST_CATEGORIES=[:]
                    TEST_PATHS_RAW=sh(
                        returnStdout: true,

                        script:"""
                            cd $DATA_HOME
                            find . -type f
                        """
                    ).split("\n") as List
                    
                    TEST_PATHS = externalFunctions.parseTestPaths(
                        TEST_PATHS_RAW
                    )
                    
                    results = [:]
                    TEST_PATHS.each{
                        results = externalFunctions.putInNestedMap(
                            results,
                            it, 
                            0, 
                            10
                        )
                    }
                    
                    ITEM_LIST = []
                    ITEM_LIST = externalFunctions.convertToDecisionTree(
                        results,
                        ITEM_LIST,
                        0,
                        10
                    )

                    now = new Date()
                    currentDate = now.format("yyyyMMdd", TimeZone.getTimeZone('UTC'))

                    filesToSelect = 1
                    testCaseNames = "SmokeTest_" + currentDate
                    containerQuantity = "1"
                    
                    env.FILE_SELECT = "{Additional Information=, ${testCaseNames}={selection_3=all, selection_1=functional, selection_2=smoke_tests, selection_0=protocol_verifier}}"

                    fileDetails = externalFunctions.getFileDetails(
                        filesToSelect,
                        containerQuantity,
                        FILE_SELECT,
                        fileNames
                    )

                    externalFunctions.executeTestFiles(
                        fileDetails,
                        containerQuantity,
                        env,
                        addInfo,
                        CONFIG_FILE_NAME
                    )
                }
            }
        }
    }
    
    post { always {
        archiveArtifacts artifacts: "**.zip", fingerprint: true
        tearDown(false,env.PV_BOX,"8", env.PV_DEPLOY_PATH)
    }}
}

def tearDown(boolean is_performance, String PV_BOX, String containerQuantity, String PV_DEPLOY_PATH){

    if(is_performance){
        sh(
            returnStdout: true,
            script:"""
                ssh root@${PV_BOX} "cd ${PV_DEPLOY_PATH} &&
                export PV_COMPOSE_FILE='docker-compose-1AER_${containerQuantity}AEO.yml' &&
                ./tear_down_pv.sh || true"
            """
        )
    } else {
        sh(
            returnStdout: true,
            script:"""
                ssh root@${PV_BOX} "cd ${PV_DEPLOY_PATH} &&
                ./tear_down_pv.sh || true"
            """
        )
    }
}