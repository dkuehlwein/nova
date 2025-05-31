import {
	createSignal,
	For,
	Show,
	onMount,
	createMemo,
	createEffect,
	createResource,
	onCleanup,
} from "solid-js";
import ExpandedCard from "./components/expanded-card";
import { debounce } from "@solid-primitives/scheduled";
import { api } from "./api";
import { LaneName } from "./components/lane-name";
import { NameInput } from "./components/name-input";
import { Header } from "./components/header";
import { Card } from "./components/card";
import { CardName } from "./components/card-name";
import { makePersisted } from "@solid-primitives/storage";
import { DragAndDrop } from "./components/drag-and-drop";
import './stylesheets/index.css';

function App() {
	const [lanes, setLanes] = createSignal([]);
	const [cards, setCards] = createSignal([]);
	const [sort, setSort] = makePersisted(createSignal("none"), {
		storage: localStorage,
		name: "sort",
	});
	const [sortDirection, setSortDirection] = makePersisted(createSignal("asc"), {
		storage: localStorage,
		name: "sortDirection",
	});
	const [selectedCard, setSelectedCard] = createSignal(null);
	const [search, setSearch] = createSignal("");
	const [filteredTag, setFilteredTag] = createSignal(null);
	const [tagsOptions, setTagsOptions] = createSignal([]);
	const [laneBeingRenamedName, setLaneBeingRenamedName] = createSignal(null);
	const [newLaneName, setNewLaneName] = createSignal(null);
	const [cardBeingRenamed, setCardBeingRenamed] = createSignal(null);
	const [newCardName, setNewCardName] = createSignal(null);
	const [isCreatingCard, setIsCreatingCard] = createSignal(false);

	function fetchTitle() {
		return fetch(`${api}/title`).then((res) => res.text());
	}

	const [title] = createResource(fetchTitle);

	function getTagBackgroundCssColor(tagColor) {
		const backgroundColorNumber = RegExp('[0-9]').exec(`${tagColor || '1'}`)[0];
		const backgroundColor = `var(--color-alt-${backgroundColorNumber})`;
		return backgroundColor;
	}

	function getTagsByTagNames(tags, tagNames) {
		return tagNames.map((tagName) => {
			const foundTag = tags.find(
				(tag) => tag.name.toLowerCase() === tagName.toLowerCase(),
			);
			
			let backgroundColor;
			if (foundTag?.backgroundColor) {
				backgroundColor = getTagBackgroundCssColor(foundTag.backgroundColor);
			} else {
				// Use hash-based color assignment for new tags
				const tagColorIndex = pickTagColorIndexBasedOnHash(tagName);
				backgroundColor = `var(--color-alt-${tagColorIndex + 1})`;
			}
			
			return { name: tagName, backgroundColor };
		});
	}

	async function fetchCards() {
		try {
			const tagsReq = fetch(`${api}/tags`, { method: "GET", mode: "cors" }).then(
				(res) => res.json(),
			);
			const cardsReq = fetch(`${api}/cards`, {
				method: "GET",
				mode: "cors",
			}).then((res) => res.json());
			const cardsSortReq = fetch(`${api}/sort/cards`, { method: "GET" }).then(
				(res) => res.json(),
			);
			const [tags, cardsFromApi, cardsSort] = await Promise.all([
				tagsReq,
				cardsReq,
				cardsSortReq,
			]);
			
			console.log("Raw API responses - tags:", tags, "cards:", cardsFromApi.length, "cardsSort:", cardsSort);
			
			// Handle tags - backend returns { all: [], used: [] } format
			let tagsArray = [];
			if (Array.isArray(tags)) {
				tagsArray = tags;
			} else if (tags && tags.used && Array.isArray(tags.used)) {
				tagsArray = tags.used;
			}
			
			// Handle cardsSort - convert object to flat array if needed
			let cardsSortArray = [];
			if (Array.isArray(cardsSort)) {
				cardsSortArray = cardsSort;
			} else if (cardsSort && typeof cardsSort === 'object') {
				// Convert object like {"Todo": ["card1"], "Doing": ["card2"]} to flat array
				cardsSortArray = Object.values(cardsSort).flat();
			}
			
			console.log("Processed data - tags:", tagsArray.length, "cardsSort:", cardsSortArray.length);
			
			setTagsOptions(tagsArray);
			
			const cardsFromApiAndSorted = cardsSortArray
				.map((cardNameFromLocalStorage) =>
					cardsFromApi.find(
						(cardFromApi) => cardFromApi.name === cardNameFromLocalStorage,
					),
				)
				.filter((card) => !!card);
			const cardsFromApiNotYetSorted = cardsFromApi.filter(
				(card) =>
					!cardsSortArray.find(
						(cardNameFromLocalStorage) => cardNameFromLocalStorage === card.name,
					),
			);
			const newCards = [...cardsFromApiAndSorted, ...cardsFromApiNotYetSorted];
			
			const newCardsWithTags = newCards.map((card) => {
				const newCard = structuredClone(card);
				const cardTagsNames = getTags(card.content) || [];
				newCard.tags = getTagsByTagNames(tagsArray, cardTagsNames);
				return newCard;
			});
			console.log("Final cards to display:", newCardsWithTags.length);
			setCards(newCardsWithTags);
		} catch (error) {
			console.error("Error fetching cards:", error);
		}
	}

	async function fetchLanes() {
		const lanesFromApiReq = fetch(`${api}/lanes`, {
			method: "GET",
			mode: "cors",
		}).then((res) => res.json());
		const lanesSortedReq = fetch(`${api}/sort/lanes`, { method: "GET" }).then(
			(res) => res.json(),
		);
		const [lanesFromApi, lanesSorted] = await Promise.all([
			lanesFromApiReq,
			lanesSortedReq,
		]);
		const lanesFromApiAndSorted = lanesSorted
			.filter((sortedLane) => lanesFromApi.find((lane) => lane === sortedLane))
			.map((lane) => lanesFromApi.find((laneFromApi) => laneFromApi === lane));
		const lanesFromApiNotYetSorted = lanesFromApi.filter(
			(lane) => !lanesSorted.includes(lane),
		);
		setLanes([...lanesFromApiAndSorted, ...lanesFromApiNotYetSorted]);
	}

	function pickTagColorIndexBasedOnHash(value) {
		let hash = 0;
		for (let i = 0; i < value.length; i++) {
			hash = value.charCodeAt(i) + ((hash << 5) - hash);
		}
		const tagOptionsLength = 7;
		const colorIndex = Math.abs(hash % tagOptionsLength);
		return colorIndex;
	}

	const debounceChangeCardContent = debounce(
		(newContent) => changeCardContent(newContent),
		250,
	);

	async function changeCardContent(newContent) {
		const newCards = structuredClone(cards());
		const newCardIndex = structuredClone(
			newCards.findIndex(
				(card) =>
					card.name === selectedCard().name &&
					card.lane === selectedCard().lane,
			),
		);
		const newCard = newCards[newCardIndex];
		newCard.content = newContent;
		await fetch(`${api}/lanes/${newCard.lane}/cards/${newCard.id}`, {
			method: "PUT",
			mode: "cors",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: newContent }),
		});
		const newTagsResponse = await fetch(`${api}/tags`, {
			method: "GET",
			mode: "cors",
		}).then((res) => res.json());
		
		// Handle the tags API response format {all: [], used: []}
		let newTagsOptions = [];
		if (Array.isArray(newTagsResponse)) {
			newTagsOptions = newTagsResponse;
		} else if (newTagsResponse && newTagsResponse.used && Array.isArray(newTagsResponse.used)) {
			newTagsOptions = newTagsResponse.used;
		}
		
		const justAddedTags = newTagsOptions.filter(
			(newTagOption) =>
				!tagsOptions().some(
					(tagOption) => tagOption.name === newTagOption.name,
				),
		);
		for (const tag of justAddedTags) {
			const tagColorIndex = pickTagColorIndexBasedOnHash(tag.name);
			const newColor = `var(--color-alt-${tagColorIndex + 1})`;
			await fetch(`${api}/tags/${tag.name}`, {
				method: "PATCH",
				mode: "cors",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					backgroundColor: newColor,
				}),
			});
			const newTagOptionIndex = newTagsOptions.findIndex(
				(newTag) => newTag.name === tag.name,
			);
			newTagsOptions[newTagOptionIndex].backgroundColor = newColor;
		}
		setTagsOptions(newTagsOptions);
		const cardTagsNames = getTags(newContent);
		newCard.tags = getTagsByTagNames(newTagsOptions, cardTagsNames);
		newCards[newCardIndex] = newCard;
		setCards(newCards);
		setSelectedCard(newCard);
	}

	function getTags(text) {
		return (text.match(/#[a-zA-Z0-9_]+/g) || []).map((tag) => tag.slice(1));
	}

	function handleSortSelectOnChange(e) {
		const value = e.target.value;
		if (value === "none") {
			setSort("none");
			return setSortDirection("asc");
		}
		const [newSort, newSortDirection] = value.split(":");
		setSort(newSort);
		setSortDirection(newSortDirection);
	}

	function handleFilterSelectOnChange(e) {
		const value = e.target.value;
		if (value === "none") {
			return setFilteredTag(null);
		}
		setFilteredTag(value);
	}

	async function createNewCard(lane) {
		if (isCreatingCard()) {
			console.log("Card creation already in progress");
			return;
		}
		
		try {
			setIsCreatingCard(true);
			console.log("Creating new card in lane:", lane);
			const newCardId = await fetch(`${api}/cards`, {
				method: "POST",
				mode: "cors",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ lane: lane }),
			}).then((res) => res.text());
			
			console.log("Created card with ID:", newCardId);
			
			// Refresh cards from API to ensure consistency
			await fetchCards();
			
			console.log("Cards after fetch:", cards().length);
			
			// Use requestAnimationFrame to ensure UI has updated before starting rename
			requestAnimationFrame(() => {
				const newCard = cards().find(card => card.id === newCardId && card.lane === lane);
				if (newCard) {
					console.log("Found new card, starting rename:", newCard);
					startRenamingCard(newCard);
				} else {
					console.error("Could not find newly created card with ID:", newCardId, "in lane:", lane);
					console.error("Available cards:", cards().map(c => ({ id: c.id, name: c.name, lane: c.lane })));
				}
			});
		} catch (error) {
			console.error("Error creating new card:", error);
		} finally {
			setIsCreatingCard(false);
		}
	}

	async function deleteCard(card) {
		await fetch(`${api}/lanes/${card.lane}/cards/${card.id}`, {
			method: "DELETE",
			mode: "cors",
		});
		
		// Refresh cards from API to ensure consistency
		await fetchCards();
	}

	async function createNewLane() {
		const newLanes = structuredClone(lanes());
		const newName = await fetch(`${api}/lanes`, {
			method: "POST",
			mode: "cors",
			headers: { "Content-Type": "application/json" },
		}).then((res) => res.text());
		newLanes.push(newName);
		setLanes(newLanes);
		setNewLaneName(newName);
		setLaneBeingRenamedName(newName);
	}

	function renameLane() {
		fetch(`${api}/lanes/${laneBeingRenamedName()}`, {
			method: "PATCH",
			mode: "cors",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ name: newLaneName() }),
		});
		const newLanes = structuredClone(lanes());
		const newLaneIndex = newLanes.findIndex(
			(laneToFind) => laneToFind === laneBeingRenamedName(),
		);
		const newLane = newLanes[newLaneIndex];
		const newCards = structuredClone(cards()).map((card) => ({
			...card,
			lane: card.lane === newLane ? newLaneName() : card.lane,
		}));
		setCards(newCards);
		newLanes[newLaneIndex] = newLaneName();
		setLanes(newLanes);
		setNewLaneName(null);
		setLaneBeingRenamedName(null);
	}

	function deleteLane(lane) {
		fetch(`${api}/lanes/${lane}`, {
			method: "DELETE",
			mode: "cors",
		});
		const newLanes = structuredClone(lanes());
		const lanesWithoutDeletedCard = newLanes.filter(
			(laneToFind) => laneToFind !== lane,
		);
		setLanes(lanesWithoutDeletedCard);
		const newCards = cards().filter((card) => card.lane !== lane);
		setCards(newCards);
	}

	function sortCardsByName() {
		const newCards = structuredClone(cards());
		return newCards.sort((a, b) =>
			sortDirection() === "asc"
				? a.name?.localeCompare(b.name)
				: b.name?.localeCompare(a.name),
		);
	}

	function sortCardsByTags() {
		const newCards = structuredClone(cards());
		return newCards.sort((a, b) => {
			return sortDirection() === "asc"
				? a.tags[0]?.name.localeCompare(b.tags?.[0])
				: b.tags[0]?.name.localeCompare(a.tags?.[0]);
		});
	}

	function handleOnSelectedCardNameChange(newName) {
		const newCards = structuredClone(cards());
		const newCardIndex = structuredClone(
			newCards.findIndex(
				(card) =>
					card.name === selectedCard().name &&
					card.lane === selectedCard().lane,
			),
		);
		const newCard = newCards[newCardIndex];
		newCard.name = newName;
		newCards[newCardIndex] = newCard;
		setCards(newCards);
		setSelectedCard(newCard);
	}

	async function handleDeleteCardsByLane(lane) {
		const cardsToDelete = cards().filter((card) => card.lane === lane);
		for (const card of cardsToDelete) {
			await fetch(`${api}/lanes/${card.lane}/cards/${card.id}`, { method: "DELETE", mode: "cors" });
		}
		
		// Refresh cards from API to ensure consistency
		await fetchCards();
	}

	async function renameCard() {
		const newCards = structuredClone(cards());
		const newCardIndex = newCards.findIndex(
			(card) => card.name === cardBeingRenamed()?.name,
		);
		const newCard = newCards[newCardIndex];
		const newCardNameWithoutSpaces = newCardName().trim();
		
		await fetch(`${api}/lanes/${newCard.lane}/cards/${newCard.id}/rename`, {
			method: "PATCH",
			mode: "cors",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ name: newCardNameWithoutSpaces }),
		});
		
		setCardBeingRenamed(null);
		
		// Refresh cards from API to ensure consistency
		await fetchCards();
	}

	async function handleTagColorChange() {
		await fetchCards();
		const newCardIndex = structuredClone(
			cards().findIndex(
				(card) =>
					card.name === selectedCard().name &&
					card.lane === selectedCard().lane,
			),
		);
		setSelectedCard(cards()[newCardIndex]);
	}

	const sortedCards = createMemo(() => {
		if (sort() === "none") {
			return cards();
		}
		if (sort() === "name") {
			return sortCardsByName();
		}
		if (sort() === "tags") {
			return sortCardsByTags();
		}
		return cards();
	});

	function validateName(newName, namesList, item) {
		if (newName === null) {
			return null;
		}
		if (newName === "") {
			return `The ${item} must have a name`;
		}
		if (namesList.filter((name) => name === (newName || "").trim()).length) {
			return `There's already a ${item} with that name`;
		}
		if (/[<>:"/\\|?*]/g.test(newName)) {
			return `The new name cannot have any of the following chracters: <>:"/\\|?*`;
		}
		return null;
	}

	function startRenamingLane(lane) {
		setNewLaneName(lane);
		setLaneBeingRenamedName(lane);
	}

	const filteredCards = createMemo(() =>
		sortedCards()
			.filter(
				(card) =>
					card.name.toLowerCase().includes(search().toLowerCase()) ||
					(card.content || "").toLowerCase().includes(search().toLowerCase()),
			)
			.filter(
				(card) =>
					filteredTag() === null ||
					card.tags
						?.map((tag) => tag.name?.toLowerCase())
						.includes(filteredTag().toLowerCase()),
			),
	);

	function getCardsFromLane(lane) {
		return filteredCards().filter((card) => card.lane === lane);
	}

	function startRenamingCard(card) {
		setNewCardName(card.name);
		setCardBeingRenamed(card);
	}

	onMount(() => {
		const url = window.location.href;
		if (!url.match(/\/$/)) {
			window.location.replace(`${url}/`);
		}
		fetchCards();
		fetchLanes();
	});

	createEffect(() => {
		if (title()) {
			document.title = title();
		}
	});

	createEffect(() => {
		if (!lanes().length) {
			return;
		}
		fetch(`${api}/lanes/sort`, {
			method: "PUT",
			body: JSON.stringify(lanes()),
			headers: {
				Accept: "application/json",
				"Content-Type": "application/json",
			},
		});
		if (disableCardsDrag()) {
			return;
		}
		
		// Build cards sort data structure: { lane: [cardNames] }
		const cardsSortData = {};
		lanes().forEach((lane) => {
			const laneCards = cards().filter((card) => card.lane === lane);
			cardsSortData[lane] = laneCards.map((card) => card.name);
		});
		
		fetch(`${api}/cards/sort`, {
			method: "PUT",
			body: JSON.stringify(cardsSortData),
			headers: {
				Accept: "application/json",
				"Content-Type": "application/json",
			},
		});
	});

	function handleLanesSortChange(changedLane) {
		const lane = lanes().find(
			(lane) => lane === changedLane.id.slice("lane-".length),
		);
		const newLanes = JSON.parse(JSON.stringify(lanes())).filter(
			(newLane) => newLane !== lane,
		);
		setLanes([
			...newLanes.slice(0, changedLane.index),
			lane,
			...newLanes.slice(changedLane.index),
		]);
	}

	function handleCardsSortChange(changedCard) {
		const cardLane = changedCard.to.slice("lane-content-".length);
		const cardId = changedCard.id.slice("card-".length);
		const oldIndex = cards().findIndex((card) => card.id === cardId);
		const oldCard = cards()[oldIndex];
		
		fetch(`${api}/lanes/${oldCard.lane}/cards/${oldCard.id}`, {
			method: "PATCH",
			mode: "cors",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ lane: cardLane }),
		});
		
		const newCard = cards()[oldIndex];
		newCard.lane = cardLane;
		const newCards = lanes().flatMap((lane) => {
			let laneCards = cards().filter(
				(card) => card.lane === lane && card.id !== cardId,
			);
			if (lane === cardLane) {
				laneCards = [
					...laneCards.slice(0, changedCard.index),
					newCard,
					...laneCards.slice(changedCard.index),
				];
			}
			return laneCards;
		});
		setCards(newCards);
	}

	const disableCardsDrag = createMemo(() => sort() !== "none");

	return (
		<>
			<Header
				search={search()}
				onSearchChange={setSearch}
				sort={sort() === "none" ? "none" : `${sort()}:${sortDirection()}`}
				onSortChange={handleSortSelectOnChange}
				tagOptions={tagsOptions().map((option) => option.name)}
				filteredTag={filteredTag()}
				onTagChange={handleFilterSelectOnChange}
				onNewLaneBtnClick={createNewLane}
			/>
			{title() ? <h1 class="app-title">{title()}</h1> : <></>}
			<DragAndDrop.Provider>
				<DragAndDrop.Container class="lanes" onChange={handleLanesSortChange}>
					<For each={lanes()}>
						{(lane) => (
							<div class="lane" id={`lane-${lane}`}>
								<header class="lane__header">
									{laneBeingRenamedName() === lane ? (
										<NameInput
											value={newLaneName()}
											errorMsg={validateName(
												newLaneName(),
												lanes().filter(
													(lane) => lane !== laneBeingRenamedName(),
												),
												"lane",
											)}
											onChange={(newValue) => setNewLaneName(newValue)}
											onConfirm={renameLane}
											onCancel={() => {
												setNewLaneName(null);
												setLaneBeingRenamedName(null);
											}}
										/>
									) : (
										<LaneName
											name={lane}
											count={getCardsFromLane(lane).length}
											onRenameBtnClick={() => startRenamingLane(lane)}
											onCreateNewCardBtnClick={() => createNewCard(lane)}
											onDelete={() => deleteLane(lane)}
											onDeleteCards={() => handleDeleteCardsByLane(lane)}
											isCreatingCard={isCreatingCard()}
										/>
									)}
								</header>
								<DragAndDrop.Container
									class="lane__content"
									group="cards"
									id={`lane-content-${lane}`}
									onChange={handleCardsSortChange}
								>
									<For each={getCardsFromLane(lane)}>
										{(card) => (
											<Card
												name={card.name}
												id={card.id}
												tags={card.tags}
												onClick={() => setSelectedCard(card)}
												headerSlot={
													cardBeingRenamed()?.name === card.name ? (
														<NameInput
															value={newCardName()}
															errorMsg={validateName(
																newCardName(),
																cards()
																	.filter(
																		(card) =>
																			card.name !== cardBeingRenamed().name,
																	)
																	.map((card) => card.name),
																"card",
															)}
															onChange={(newValue) => setNewCardName(newValue)}
															onConfirm={renameCard}
															onCancel={() => {
																setNewCardName(null);
																setCardBeingRenamed(null);
															}}
														/>
													) : (
														<CardName
															name={card.name}
															hasContent={!!card.content}
															onRenameBtnClick={() => startRenamingCard(card)}
															onDelete={() => deleteCard(card)}
															onClick={() => setSelectedCard(card)}
														/>
													)
												}
											/>
										)}
									</For>
								</DragAndDrop.Container>
							</div>
						)}
					</For>
				</DragAndDrop.Container>
				<DragAndDrop.Target />
			</DragAndDrop.Provider>
			<Show when={!!selectedCard()}>
				<ExpandedCard
					name={selectedCard().name}
					id={selectedCard().id}
					lane={selectedCard().lane}
					content={selectedCard().content}
					tags={selectedCard().tags || []}
					tagsOptions={tagsOptions()}
					onClose={() => setSelectedCard(null)}
					onContentChange={(value) =>
						debounceChangeCardContent(value, selectedCard().id)
					}
					onTagColorChange={handleTagColorChange}
					onNameChange={handleOnSelectedCardNameChange}
					getNameErrorMsg={(newName) =>
						validateName(
							newName,
							cards()
								.filter((card) => card.name !== selectedCard().name)
								.map((card) => card.name),
							"card",
						)
					}
					disableImageUpload={false}
				/>
			</Show>
		</>
	);
}

export default App;
