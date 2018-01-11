pipeline {
  agent none

  stages {

    stage('Stash'){
      agent any
      steps{
        sh'''
          git rev-parse HEAD > hash
        '''
        stash name:'dev_stash', includes: 'hash' //stores the commit head in a stash
      }
    }

    stage ('Lint') { //checks if format is okay
      agent any
      steps {
        unstash 'dev_stash' //unstashes the dev_stash
        sh'''
          git reset --hard $(cat hash)
          echo "Nothing to lint..."
        '''
      }
    }

    stage('Testing') {
      agent any
      steps {
        unstash 'dev_stash' //unstashes the dev_stash
        sh '''
          git reset --hard $(cat hash)
          echo "Nothing to test..."
        '''
      }
    }
  }
}