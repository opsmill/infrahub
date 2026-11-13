import React from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading'
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './styles.module.css';
import { translate } from '@docusaurus/Translate';
import ArrowRightIcon from "@site/static/img/arrow-right.svg";
import EducationIcon from "@site/static/img/education.svg";

export default function HomepageHeader() {
    const { siteConfig } = useDocusaurusContext();
    const screenshotUrl = useBaseUrl('/img/readme-screenshots/dashboard.webp');

    return (
        <header className={clsx('container', styles.heroBanner)}>
            <div className="col col--6">
                <Heading as="h1" className={clsx("hero__title", styles.heroTitle)}>
                    {translate({
                        id: 'home.header.title',
                        message: 'Infrahub Docs',
                    })}
                </Heading>
                <p className="hero__subtitle">
                    {translate({
                        id: 'home.header.subtitle',
                        message: "The data foundation for network, data center, and cloud automation.",
                    })}
                </p>

                <div className={styles.containerFlexWrap}>
                    <Link
                        className={clsx(styles.heroButton, "button button--primary button--lg")}
                        to="https://sandbox.infrahub.app/"
                    >
                        {translate({
                            id: 'home.header.sandbox',
                            message: 'Infrahub Sandbox',
                        })}
                        <ArrowRightIcon />
                    </Link>
                    <Link
                        className={clsx(styles.heroButton, "button button--secondary button--lg")}
                        to="https://docs.infrahub.app/labs"
                    >
                        {translate({
                            id: 'home.header.tutorials',
                            message: 'Infrahub Labs',
                        })}
                        <EducationIcon />
                    </Link>
                </div>
            </div>

            <div className={clsx(styles.infrahubScreenshot, "col col--6")}>
                <img
                    src={screenshotUrl}
                    alt="The Infrahub web interface listing devices, with the branch selector set to main"
                    loading="eager"
                />
            </div>
        </header>
    );
}
