Fixed startup failing on a CA bundle setting left empty, such as a blanked `INFRAHUB_TLS_CA_BUNDLE` or `AWS_CA_BUNDLE` variable; an empty value is now read as unset
