import React from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading'
import Link from '@docusaurus/Link';
import styles from './styles.module.css';

type SectionItem = {
    title: string;
    svgPath: string;
    description: React.ReactNode;
    link: string;
};

export default function HomePageCard({ title, svgPath, description, link }: SectionItem) {
    return (
        <div className='flex col col--4 margin-bottom--md'>
            <Link to={link} className={clsx(styles.heroCard, "card text--no-decoration")}>
                <div className={clsx("card__header", styles.cardTitle)}>
                    <img src={svgPath} width="24px" alt="python logo" />
                    <Heading as="h3">{title}</Heading>
                </div>

                <div className="card__body">{description}</div>
            </Link>
        </div>
    )
}