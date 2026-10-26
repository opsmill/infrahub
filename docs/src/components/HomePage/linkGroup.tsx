import React from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading'
import Link from '@docusaurus/Link';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './styles.module.css';

type GroupLink = {
    label: string;
    to: string;
};

type LinkGroupItem = {
    title: string;
    svgPath?: string;
    description: React.ReactNode;
    links: GroupLink[];
};

export default function HomePageLinkGroup({ title, svgPath, description, links }: LinkGroupItem) {
    const imgSrc = useBaseUrl(svgPath ?? '');

    return (
        <div className={clsx('flex col col--3 margin-bottom--md', styles.groupCol)}>
            <div className={clsx(styles.groupCard, "card")}>
                <div className={clsx("card__header", styles.cardTitle)}>
                    {svgPath && <img src={imgSrc} width="24px" alt="" />}
                    <Heading as="h3">{title}</Heading>
                </div>

                <div className="card__body">
                    <p>{description}</p>
                    <ul className={styles.groupLinks}>
                        {links.map((link) => (
                            <li key={link.to}>
                                <Link to={link.to}>{link.label}</Link>
                            </li>
                        ))}
                    </ul>
                </div>
            </div>
        </div>
    )
}
