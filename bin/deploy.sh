#!/usr/bin/env bash

BRANCH=${1:-}
TAG=${2:-${TAG}}

git clone git@github.com:singlecomm/kubernetes-config.git -b "${BRANCH}" "kubernetes-config-${BRANCH}"
sed -i "s/singlecomm\\/amazon-redshift-utils:v[0-9]\\+.[0-9]\\+.[0-9]\\+/singlecomm\\/amazon-redshift-utils:$TAG/" kubernetes-config-${BRANCH}/${BRANCH}-coral/cronjobs/analyze-vacuum-redshift.yml
kubectl --context="${BRANCH}" --namespace="${BRANCH}-coral" apply -f kubernetes-config-${BRANCH}/${BRANCH}-coral/cronjobs/analyze-vacuum-redshift.yml
cd kubernetes-config-${BRANCH}
git add ${BRANCH}-coral/cronjobs/analyze-vacuum-redshift.yml
git commit -m "chore(release): Amazon Redshift Utils Version $TAG"
git push origin ${BRANCH}
