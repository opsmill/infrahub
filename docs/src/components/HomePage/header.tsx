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
    const videoUrl = useBaseUrl('/medias/demo.mp4');

    return (
        <header className={clsx('container', styles.heroBanner)}>
            <div className="col col--6">
                <Heading as="h1" className="hero__title">{siteConfig.title}</Heading>
                <p className="hero__subtitle">
                    {translate({
                        id: 'home.header.subtitle',
                        message: "Infrastructure Data Management Platform",
                    })}
                </p>

                <div className={styles.containerFlexWrap}>
                    <Link
                        className={clsx(styles.heroButton, "button button--primary button--lg")}
                        to="overview"
                    >
                        {translate({
                            id: 'home.header.docs',
                            message: 'Learn about Infrahub',
                        })}

                        <ArrowRightIcon />
                    </Link>
                    <Link
                        className={clsx(styles.heroButton, "button button--secondary button--lg")}
                        to="overview/community-vs-enterprise"
                    >
                        {translate({
                            id: 'home.header.editions',
                            message: 'Community vs Enterprise',
                        })}
                        <ArrowRightIcon />
                    </Link>
                    <Link
                        className={clsx(styles.heroButton, "button button--secondary button--lg")}
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
                        to="https://opsmill.instruqt.com/pages/labs"
                    >
                        {translate({
                            id: 'home.header.tutorials',
                            message: 'Infrahub Labs',
                        })}
                        <EducationIcon />
                    </Link>
                </div>
            </div>

            <div className={clsx(styles.infrahubVideo, "col col--6")}>
                <video
                    style={{
                        pointerEvents: "none",
                        maxHeight: "540px"
                    }}
                    className="rounded-2xl" height="100%" loop autoPlay muted>
                    <source src={videoUrl} type="video/mp4" />
                </video>
            </div>
        </header>
    );
}
